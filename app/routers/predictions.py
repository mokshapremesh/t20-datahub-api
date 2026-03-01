from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import Optional
import math
from app.db.session import get_session
from app.models.prediction import PredictionModel, MatchModelPrediction, UserPrediction, Transaction
from app.models.match import Match
from app.models.user import User
from app.services.auth import get_current_user
from app.services.prediction_engine import compute_prediction

router = APIRouter(prefix="/predictions", tags=["Cricket Prediction League"])


def compute_multiplier(probability: float) -> float:
    """Difficulty multiplier — harder pick = more Fan Points. Capped 1.0x–3.0x"""
    raw = 1 / probability if probability > 0 else 3.0
    return round(min(3.0, max(1.0, raw)), 2)


async def get_or_create_model(session: AsyncSession) -> PredictionModel:
    model = (await session.execute(
        select(PredictionModel).where(PredictionModel.is_active == True)
    )).scalar_one_or_none()
    if not model:
        model = PredictionModel(
            name="WeightedFactors-v1",
            model_type="statistical",
            features=["batting", "bowling", "powerplay", "death_batting", "death_bowling", "venue", "h2h", "form"],
            trained_on="2014-2024",
            is_active=True,
        )
        session.add(model)
        await session.flush()
    return model


# ═══════════════════════════════════════════════════════════════════════════════
# PUBLIC ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/predict")
async def predict_any_match(
    team1: str = Query(..., description="e.g. India"),
    team2: str = Query(..., description="e.g. Pakistan"),
    venue: Optional[str] = Query(None, description="e.g. Eden Gardens, Kolkata"),
    session: AsyncSession = Depends(get_session),
):
    """
    Get AI model prediction for any T20 match — past, present or future.
    No auth needed. Uses 8 cricket-native factors from ball-by-ball data.
    """
    if not venue:
        v = (await session.execute(
            select(Match.venue).where(
                ((Match.team1 == team1) & (Match.team2 == team2)) |
                ((Match.team1 == team2) & (Match.team2 == team1))
            ).order_by(Match.match_date.desc()).limit(1)
        )).scalar()
        venue = v or "Neutral Venue"

    prob = await compute_prediction(team1, team2, venue, session)
    t1_prob = prob["win_probability"][team1]
    t2_prob = prob["win_probability"][team2]

    return {
        "matchup": f"{team1} vs {team2}",
        "venue": venue,
        "model_prediction": prob["predicted_winner"],
        "confidence": prob["confidence"],
        "win_probability": {
            team1: f"{round(t1_prob * 100, 1)}%",
            team2: f"{round(t2_prob * 100, 1)}%",
        },
        "if_you_predict": {
            team1: {
                "difficulty_multiplier": f"{compute_multiplier(t1_prob)}x",
                "fan_points_per_100_boost": int(100 * compute_multiplier(t1_prob)),
            },
            team2: {
                "difficulty_multiplier": f"{compute_multiplier(t2_prob)}x",
                "fan_points_per_100_boost": int(100 * compute_multiplier(t2_prob)),
            },
        },
        "factor_analysis": prob["factors"],
        "matchup_summary": prob["matchup_summary"],
        "tip": (
            f"Model strongly backs {prob['predicted_winner']} — "
            f"picking the other team pays {compute_multiplier(min(t1_prob, t2_prob))}x boost."
        ),
    }


@router.get("/leaderboard")
async def leaderboard(
    limit: int = Query(10),
    session: AsyncSession = Depends(get_session),
):
    """Public leaderboard — top Fan Point holders"""
    users = (await session.execute(
        select(User).order_by(User.points_balance.desc()).limit(limit)
    )).scalars().all()

    board = []
    for i, u in enumerate(users):
        total = (await session.execute(
            select(func.count(UserPrediction.id)).where(UserPrediction.user_id == u.id)
        )).scalar() or 0
        correct = (await session.execute(
            select(func.count(UserPrediction.id)).where(
                UserPrediction.user_id == u.id,
                UserPrediction.status == "SETTLED",
                UserPrediction.profit_points > 0,
            )
        )).scalar() or 0
        board.append({
            "rank": i + 1,
            "username": u.username,
            "fan_points": u.points_balance,
            "profit_vs_start": u.points_balance - 1000,
            "predictions": total,
            "correct": correct,
            "accuracy": f"{round(correct/total*100,1)}%" if total > 0 else "N/A",
        })

    return {"leaderboard": board, "note": "All users start with 1000 Fan Points"}


# ═══════════════════════════════════════════════════════════════════════════════
# CRUD — Authenticated
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("", status_code=status.HTTP_201_CREATED)
async def create_prediction(
    body: dict,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """
    Place a prediction on a match.
    Find match by team names + year (no IDs needed).
    Optionally boost with Fan Points for higher returns.

    Body:
    {
        "team1": "India",
        "team2": "Pakistan",
        "year": "2026",
        "predicted_winner": "India",
        "boost_points": 100    ← optional, default 50
    }
    """
    team1 = body.get("team1", "").strip()
    team2 = body.get("team2", "").strip()
    year = str(body.get("year", "2026"))
    predicted_winner = body.get("predicted_winner", "").strip()
    boost = int(body.get("boost_points", 50))
    date = body.get("date")

    if not all([team1, team2, predicted_winner]):
        raise HTTPException(status_code=400, detail="team1, team2 and predicted_winner are required")
    if boost < 10:
        raise HTTPException(status_code=400, detail="Minimum boost is 10 Fan Points")
    if boost > current_user.points_balance:
        raise HTTPException(
            status_code=400,
            detail=f"Not enough Fan Points. Your balance: {current_user.points_balance}"
        )

    # Find match — by team names and year
    query = select(Match).where(
        ((Match.team1 == team1) & (Match.team2 == team2)) |
        ((Match.team1 == team2) & (Match.team2 == team1)),
        Match.tournament_year == year,
    )
    if date:
        query = query.where(Match.match_date == date)

    matches = (await session.execute(query)).scalars().all()

    if not matches:
        raise HTTPException(
            status_code=404,
            detail=f"No match found: {team1} vs {team2} in {year}. "
                   f"For future matches not yet in DB, use GET /predictions/predict"
        )
    if len(matches) > 1:
        return {
            "message": "Multiple matches found between these teams in this year. Add 'date' to your request.",
            "matches": [
                {"date": str(m.match_date), "venue": m.venue, "stage": m.stage, "winner": m.winner}
                for m in matches
            ]
        }

    match = matches[0]

    if predicted_winner not in [match.team1, match.team2]:
        raise HTTPException(
            status_code=400,
            detail=f"predicted_winner must be '{match.team1}' or '{match.team2}'"
        )

    # No duplicate predictions
    existing = (await session.execute(
        select(UserPrediction).where(
            UserPrediction.user_id == current_user.id,
            UserPrediction.match_id == match.id,
        )
    )).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=400, detail="Already predicted this match. Use PUT to update.")

    # Run prediction engine
    prob = await compute_prediction(match.team1, match.team2, match.venue, session)
    model = await get_or_create_model(session)

    # Store model snapshot
    model_snap = MatchModelPrediction(
        match_id=match.id,
        model_id=model.id,
        prob_team1=prob["win_probability"][match.team1],
        prob_team2=prob["win_probability"][match.team2],
        predicted_winner=prob["predicted_winner"],
        explanation=prob["factors"],
    )
    session.add(model_snap)
    await session.flush()

    # Compute multiplier for user's pick
    pick_prob = prob["win_probability"][predicted_winner]
    multiplier = compute_multiplier(pick_prob)
    potential_return = int(boost * multiplier)
    model_agrees = (prob["predicted_winner"] == predicted_winner)

    # Deduct boost from balance
    current_user.points_balance -= boost
    session.add(Transaction(
        user_id=current_user.id, type="BOOST",
        amount=-boost, balance_after=current_user.points_balance,
        reference_type="prediction",
        note=f"Boosted prediction: {predicted_winner} to win vs "
             f"{match.team2 if predicted_winner == match.team1 else match.team1}"
    ))

    # Create prediction
    pred = UserPrediction(
        user_id=current_user.id,
        match_id=match.id,
        model_prediction_id=model_snap.id,
        picked_team=predicted_winner,
        stake_points=boost,
        odds_multiplier=multiplier,
        status="OPEN",
    )
    session.add(pred)
    await session.flush()

    # Auto-settle if match already played
    if match.winner:
        if predicted_winner == match.winner:
            pred.payout_points = potential_return
            pred.profit_points = potential_return - boost
            current_user.points_balance += potential_return
            session.add(Transaction(
                user_id=current_user.id, type="PAYOUT",
                amount=potential_return, balance_after=current_user.points_balance,
                reference_type="prediction", reference_id=pred.id,
                note=f"Correct! {predicted_winner} won. Earned {potential_return} pts"
            ))
        else:
            pred.payout_points = 0
            pred.profit_points = -boost
            session.add(Transaction(
                user_id=current_user.id, type="LOSS",
                amount=0, balance_after=current_user.points_balance,
                reference_type="prediction", reference_id=pred.id,
                note=f"Incorrect. {match.winner} won."
            ))
        pred.status = "SETTLED"

    await session.commit()
    await session.refresh(pred)

    return {
        "id": pred.id,
        "match": {
            "team1": match.team1,
            "team2": match.team2,
            "date": str(match.match_date),
            "venue": match.venue,
            "stage": match.stage,
            "tournament_year": match.tournament_year,
        },
        "your_prediction": {
            "picked_team": predicted_winner,
            "boost_points": boost,
            "difficulty_multiplier": f"{multiplier}x",
            "potential_return": potential_return,
            "potential_profit": potential_return - boost,
            "status": pred.status,
        },
        "model_says": {
            "predicted_winner": prob["predicted_winner"],
            "confidence": prob["confidence"],
            "win_probability": {
                match.team1: f"{round(prob['win_probability'][match.team1]*100,1)}%",
                match.team2: f"{round(prob['win_probability'][match.team2]*100,1)}%",
            },
        },
        "model_agrees_with_you": model_agrees,
        "verdict": (
            f"✅ Safe pick — model agrees. {multiplier}x return if correct."
            if model_agrees else
            f"⚡ Bold call! You're backing the underdog at {multiplier}x. Model favours {prob['predicted_winner']}."
        ),
        "factor_analysis": prob["factors"],
        "matchup_summary": prob["matchup_summary"],
        "fan_points": {
            "before": current_user.points_balance + boost,
            "boosted": boost,
            "current_balance": current_user.points_balance,
        },
        "result": {
            "actual_winner": match.winner,
            "payout": pred.payout_points,
            "profit": pred.profit_points,
            "verdict": "🎉 Correct prediction!" if pred.profit_points and pred.profit_points > 0 else "❌ Incorrect prediction",
        } if match.winner else "⏳ Match not yet played — prediction locked in",
    }


@router.get("")
async def get_my_predictions(
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Your full prediction history + Fan Points summary + vs model comparison"""
    preds = (await session.execute(
        select(UserPrediction)
        .where(UserPrediction.user_id == current_user.id)
        .order_by(UserPrediction.created_at.desc())
    )).scalars().all()

    settled = [p for p in preds if p.status == "SETTLED"]
    correct = [p for p in settled if p.profit_points and p.profit_points > 0]
    total_boosted = sum(p.stake_points for p in preds)
    total_returned = sum(p.payout_points or 0 for p in settled)

    # Model accuracy
    model_correct = 0
    for p in settled:
        mp = await session.get(MatchModelPrediction, p.model_prediction_id)
        m = await session.get(Match, p.match_id)
        if mp and m and m.winner:
            if mp.predicted_winner == m.winner:
                model_correct += 1

    pred_list = []
    for p in preds:
        m = await session.get(Match, p.match_id)
        pred_list.append({
            "id": p.id,
            "match": f"{m.team1} vs {m.team2}",
            "date": str(m.match_date),
            "tournament_year": m.tournament_year,
            "your_pick": p.picked_team,
            "boost_points": p.stake_points,
            "difficulty_multiplier": f"{p.odds_multiplier}x",
            "potential_return": int(p.stake_points * p.odds_multiplier),
            "status": p.status,
            "payout": p.payout_points,
            "profit": p.profit_points,
            "actual_winner": m.winner,
        })

    return {
        "username": current_user.username,
        "fan_points_balance": current_user.points_balance,
        "profit_vs_start": current_user.points_balance - 1000,
        "summary": {
            "total_predictions": len(preds),
            "settled": len(settled),
            "correct": len(correct),
            "accuracy": f"{round(len(correct)/len(settled)*100,1)}%" if settled else "N/A",
            "total_boosted": total_boosted,
            "total_returned": total_returned,
            "net_profit": total_returned - total_boosted,
        },
        "beat_the_ai": {
            "your_correct": len(correct),
            "model_correct": model_correct,
            "result": (
                "🏆 You're beating the AI!"
                if len(correct) > model_correct else
                "🤖 AI is ahead — can you catch up?"
                if model_correct > len(correct) else
                "🤝 Tied with the AI!"
            ),
        },
        "predictions": pred_list,
    }


@router.get("/{prediction_id}")
async def get_prediction(
    prediction_id: int,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    pred = (await session.execute(
        select(UserPrediction).where(
            UserPrediction.id == prediction_id,
            UserPrediction.user_id == current_user.id,
        )
    )).scalar_one_or_none()
    if not pred:
        raise HTTPException(status_code=404, detail="Prediction not found")

    match = await session.get(Match, pred.match_id)
    model_snap = await session.get(MatchModelPrediction, pred.model_prediction_id)

    return {
        "id": pred.id,
        "match": {
            "team1": match.team1,
            "team2": match.team2,
            "date": str(match.match_date),
            "venue": match.venue,
            "stage": match.stage,
            "actual_winner": match.winner,
        },
        "your_prediction": {
            "picked_team": pred.picked_team,
            "boost_points": pred.stake_points,
            "difficulty_multiplier": f"{pred.odds_multiplier}x",
            "potential_return": int(pred.stake_points * pred.odds_multiplier),
            "status": pred.status,
            "payout": pred.payout_points,
            "profit": pred.profit_points,
        },
        "model_at_time_of_prediction": {
            "predicted_winner": model_snap.predicted_winner if model_snap else None,
            "win_probability": {
                match.team1: f"{round(model_snap.prob_team1*100,1)}%" if model_snap else None,
                match.team2: f"{round(model_snap.prob_team2*100,1)}%" if model_snap else None,
            },
            "factor_breakdown": model_snap.explanation if model_snap else None,
        },
        "result": {
            "correct": pred.profit_points and pred.profit_points > 0,
            "verdict": "🎉 Correct!" if pred.profit_points and pred.profit_points > 0 else "❌ Incorrect",
            "points_change": pred.profit_points,
        } if pred.status == "SETTLED" else "⏳ Not yet settled",
    }


@router.put("/{prediction_id}")
async def update_prediction(
    prediction_id: int,
    body: dict,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """
    Update your pick or boost — only allowed while status is OPEN.
    Body: { "predicted_winner": "Pakistan", "boost_points": 150 }
    """
    pred = (await session.execute(
        select(UserPrediction).where(
            UserPrediction.id == prediction_id,
            UserPrediction.user_id == current_user.id,
        )
    )).scalar_one_or_none()
    if not pred:
        raise HTTPException(status_code=404, detail="Prediction not found")
    if pred.status != "OPEN":
        raise HTTPException(
            status_code=400,
            detail=f"Cannot update — prediction is already {pred.status}"
        )

    match = await session.get(Match, pred.match_id)
    prob = await compute_prediction(match.team1, match.team2, match.venue, session)

    if "predicted_winner" in body:
        new_pick = body["predicted_winner"].strip()
        if new_pick not in [match.team1, match.team2]:
            raise HTTPException(
                status_code=400,
                detail=f"Must be '{match.team1}' or '{match.team2}'"
            )
        pred.picked_team = new_pick
        new_mult = compute_multiplier(prob["win_probability"][new_pick])
        pred.odds_multiplier = new_mult

    if "boost_points" in body:
        new_boost = int(body["boost_points"])
        diff = new_boost - pred.stake_points
        if diff > current_user.points_balance:
            raise HTTPException(status_code=400, detail="Insufficient Fan Points")
        current_user.points_balance -= diff
        pred.stake_points = new_boost

    await session.commit()

    return {
        "message": "Prediction updated ✅",
        "id": pred.id,
        "match": f"{match.team1} vs {match.team2} ({match.match_date})",
        "picked_team": pred.picked_team,
        "boost_points": pred.stake_points,
        "difficulty_multiplier": f"{pred.odds_multiplier}x",
        "potential_return": int(pred.stake_points * pred.odds_multiplier),
        "fan_points_balance": current_user.points_balance,
    }


@router.delete("/{prediction_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_prediction(
    prediction_id: int,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Withdraw prediction — only if OPEN. Boost points refunded."""
    pred = (await session.execute(
        select(UserPrediction).where(
            UserPrediction.id == prediction_id,
            UserPrediction.user_id == current_user.id,
        )
    )).scalar_one_or_none()
    if not pred:
        raise HTTPException(status_code=404, detail="Prediction not found")
    if pred.status != "OPEN":
        raise HTTPException(
            status_code=400,
            detail=f"Cannot withdraw — prediction is {pred.status}"
        )

    # Refund boost
    current_user.points_balance += pred.stake_points
    session.add(Transaction(
        user_id=current_user.id, type="REFUND",
        amount=pred.stake_points, balance_after=current_user.points_balance,
        reference_type="prediction", reference_id=pred.id,
        note="Prediction withdrawn — boost refunded"
    ))
    await session.delete(pred)
    await session.commit()
