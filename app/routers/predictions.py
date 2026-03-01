from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.db.session import get_session
from app.models.prediction import MatchPrediction
from app.models.match import Match
from app.models.delivery import Delivery
from app.models.user import User
from app.services.auth import get_current_user

router = APIRouter(prefix="/predictions", tags=["Match Predictions"])


# ─── Probability Engine ───────────────────────────────────────────────────────

async def calculate_win_probability(
    team1: str, team2: str, venue: str, session: AsyncSession
) -> dict:

    # ── Factor 1: Head to Head (40% weight) ──────────────────────────────────
    h2h_result = await session.execute(
        select(
            func.count(Match.id).label("total"),
            func.count(Match.id).filter(Match.winner == team1).label("team1_wins"),
        ).where(
            ((Match.team1 == team1) & (Match.team2 == team2)) |
            ((Match.team1 == team2) & (Match.team2 == team1)),
            Match.winner != None,
        )
    )
    h2h = h2h_result.first()
    total_h2h = h2h.total or 0
    team1_h2h_wins = h2h.team1_wins or 0
    h2h_rate = (team1_h2h_wins / total_h2h) if total_h2h > 0 else 0.5

    # ── Factor 2: Venue — batting first win rate (30% weight) ────────────────
    venue_result = await session.execute(
        select(
            func.count(Match.id).label("total"),
            func.count(Match.id).filter(
                ((Match.toss_decision == "bat") & (Match.toss_winner == Match.winner)) |
                ((Match.toss_decision == "field") & (Match.toss_winner != Match.winner))
            ).label("batting_first_wins"),
        ).where(
            Match.venue == venue,
            Match.winner != None,
        )
    )
    venue_row = venue_result.first()
    total_venue = venue_row.total or 0
    batting_first_wins = venue_row.batting_first_wins or 0
    venue_rate = (batting_first_wins / total_venue) if total_venue > 0 else 0.5

    # ── Factor 3: Recent form — last 5 WC matches (30% weight) ───────────────
    team1_recent = await session.execute(
        select(Match).where(
            (Match.team1 == team1) | (Match.team2 == team1),
            Match.winner != None,
            Match.tournament_year != "2026",
        ).order_by(Match.match_date.desc()).limit(5)
    )
    team1_matches = team1_recent.scalars().all()
    team1_recent_wins = sum(1 for m in team1_matches if m.winner == team1)
    team1_form = (team1_recent_wins / len(team1_matches)) if team1_matches else 0.5

    team2_recent = await session.execute(
        select(Match).where(
            (Match.team1 == team2) | (Match.team2 == team2),
            Match.winner != None,
            Match.tournament_year != "2026",
        ).order_by(Match.match_date.desc()).limit(5)
    )
    team2_matches = team2_recent.scalars().all()
    team2_recent_wins = sum(1 for m in team2_matches if m.winner == team2)
    team2_form = (team2_recent_wins / len(team2_matches)) if team2_matches else 0.5

    # Normalize form so team1 + team2 form = 1
    total_form = team1_form + team2_form
    form_rate = (team1_form / total_form) if total_form > 0 else 0.5

    # ── Final weighted probability ────────────────────────────────────────────
    team1_prob = round(
        (0.40 * h2h_rate) +
        (0.30 * venue_rate) +
        (0.30 * form_rate),
        3
    )
    team2_prob = round(1 - team1_prob, 3)

    # Confidence based on data availability
    if total_h2h >= 5 and total_venue >= 3:
        confidence = "High"
    elif total_h2h >= 2 or total_venue >= 2:
        confidence = "Medium"
    else:
        confidence = "Low — limited historical data"

    model_prediction = team1 if team1_prob >= 0.5 else team2

    return {
        "win_probability": {
            team1: team1_prob,
            team2: team2_prob,
        },
        "model_prediction": model_prediction,
        "confidence": confidence,
        "analysis": {
            "head_to_head": {
                "total_meetings": total_h2h,
                f"{team1}_wins": team1_h2h_wins,
                f"{team2}_wins": total_h2h - team1_h2h_wins,
                "h2h_win_rate": round(h2h_rate, 3),
                "weight": "40%",
            },
            "venue_history": {
                "matches_at_venue": total_venue,
                "batting_first_win_pct": round(venue_rate * 100, 1),
                "weight": "30%",
            },
            "recent_form": {
                f"{team1}_last_5_wins": team1_recent_wins,
                f"{team2}_last_5_wins": team2_recent_wins,
                "form_rate": round(form_rate, 3),
                "weight": "30%",
            },
        },
        "based_on_matches": 216,
    }


# ─── CRUD Endpoints ───────────────────────────────────────────────────────────

@router.post("", status_code=status.HTTP_201_CREATED)
async def create_prediction(
    body: dict,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    match_id = body.get("match_id")
    predicted_winner = body.get("predicted_winner")

    # Validate match exists and is 2026
    result = await session.execute(select(Match).where(Match.id == match_id))
    match = result.scalar_one_or_none()
    if not match:
        raise HTTPException(status_code=404, detail="Match not found")
    if match.tournament_year != "2026":
        raise HTTPException(
            status_code=400,
            detail="You can only predict 2026 tournament matches"
        )
    if predicted_winner not in [match.team1, match.team2]:
        raise HTTPException(
            status_code=400,
            detail=f"Predicted winner must be {match.team1} or {match.team2}"
        )

    # Check user hasn't already predicted this match
    existing = await session.execute(
        select(MatchPrediction).where(
            MatchPrediction.user_id == current_user.id,
            MatchPrediction.match_id == match_id,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=400,
            detail="You have already predicted this match. Use PUT to update."
        )

    # Run probability engine
    prob = await calculate_win_probability(
        match.team1, match.team2, match.venue, session
    )

    model_agrees = (prob["model_prediction"] == predicted_winner)

    # Save prediction
    prediction = MatchPrediction(
        user_id=current_user.id,
        match_id=match_id,
        predicted_winner=predicted_winner,
        win_prob_team1=prob["win_probability"][match.team1],
        win_prob_team2=prob["win_probability"][match.team2],
        h2h_factor=prob["analysis"]["head_to_head"]["h2h_win_rate"],
        venue_factor=prob["analysis"]["venue_history"]["batting_first_win_pct"],
        form_factor=prob["analysis"]["recent_form"]["form_rate"],
        confidence=prob["confidence"],
        model_prediction=prob["model_prediction"],
        model_agrees=model_agrees,
    )
    session.add(prediction)
    await session.commit()
    await session.refresh(prediction)

    return {
        "id": prediction.id,
        "match": {
            "id": match.id,
            "team1": match.team1,
            "team2": match.team2,
            "date": match.match_date,
            "venue": match.venue,
            "stage": match.stage,
        },
        "your_prediction": predicted_winner,
        "system_analysis": prob,
        "model_agrees_with_you": model_agrees,
        "verdict": (
            "✅ Model agrees with your prediction!"
            if model_agrees
            else f"⚠️ Model disagrees — system favours {prob['model_prediction']}"
        ),
    }


@router.get("")
async def get_my_predictions(
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    result = await session.execute(
        select(MatchPrediction).where(
            MatchPrediction.user_id == current_user.id
        ).order_by(MatchPrediction.created_at.desc())
    )
    predictions = result.scalars().all()

    # Calculate accuracy stats
    scored = [p for p in predictions if p.user_correct is not None]
    user_correct = sum(1 for p in scored if p.user_correct)
    model_correct = sum(1 for p in scored if p.model_correct)

    pred_list = []
    for p in predictions:
        match = await session.get(Match, p.match_id)
        pred_list.append({
            "id": p.id,
            "match": f"{match.team1} vs {match.team2} ({match.match_date})",
            "your_prediction": p.predicted_winner,
            "model_prediction": p.model_prediction,
            "model_agrees": p.model_agrees,
            "confidence": p.confidence,
            "actual_winner": p.actual_winner,
            "user_correct": p.user_correct,
            "model_correct": p.model_correct,
        })

    return {
        "total_predictions": len(predictions),
        "scored_predictions": len(scored),
        "accuracy": {
            "your_accuracy": f"{round(user_correct/len(scored)*100, 1)}%" if scored else "No results yet",
            "model_accuracy": f"{round(model_correct/len(scored)*100, 1)}%" if scored else "No results yet",
            "you_vs_model": (
                "You're beating the model! 🏆"
                if scored and user_correct > model_correct
                else "Model is ahead 🤖"
                if scored and model_correct > user_correct
                else "Tied!" if scored else "No results yet"
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
    result = await session.execute(
        select(MatchPrediction).where(
            MatchPrediction.id == prediction_id,
            MatchPrediction.user_id == current_user.id,
        )
    )
    prediction = result.scalar_one_or_none()
    if not prediction:
        raise HTTPException(status_code=404, detail="Prediction not found")

    match = await session.get(Match, prediction.match_id)

    return {
        "id": prediction.id,
        "match": {
            "team1": match.team1,
            "team2": match.team2,
            "date": match.match_date,
            "venue": match.venue,
            "stage": match.stage,
        },
        "your_prediction": prediction.predicted_winner,
        "model_prediction": prediction.model_prediction,
        "model_agrees": prediction.model_agrees,
        "win_probability": {
            match.team1: prediction.win_prob_team1,
            match.team2: prediction.win_prob_team2,
        },
        "confidence": prediction.confidence,
        "actual_winner": prediction.actual_winner,
        "result": {
            "user_correct": prediction.user_correct,
            "model_correct": prediction.model_correct,
        } if prediction.actual_winner else "Match not yet played",
    }


@router.put("/{prediction_id}")
async def update_prediction(
    prediction_id: int,
    body: dict,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    result = await session.execute(
        select(MatchPrediction).where(
            MatchPrediction.id == prediction_id,
            MatchPrediction.user_id == current_user.id,
        )
    )
    prediction = result.scalar_one_or_none()
    if not prediction:
        raise HTTPException(status_code=404, detail="Prediction not found")

    match = await session.get(Match, prediction.match_id)

    # Update predicted winner
    if "predicted_winner" in body:
        if body["predicted_winner"] not in [match.team1, match.team2]:
            raise HTTPException(
                status_code=400,
                detail=f"Must be {match.team1} or {match.team2}"
            )
        prediction.predicted_winner = body["predicted_winner"]
        prediction.model_agrees = (prediction.model_prediction == body["predicted_winner"])

    # Update actual winner after match is played
    if "actual_winner" in body:
        if body["actual_winner"] not in [match.team1, match.team2]:
            raise HTTPException(
                status_code=400,
                detail=f"Actual winner must be {match.team1} or {match.team2}"
            )
        prediction.actual_winner = body["actual_winner"]
        prediction.user_correct = (prediction.predicted_winner == body["actual_winner"])
        prediction.model_correct = (prediction.model_prediction == body["actual_winner"])

    await session.commit()

    return {
        "message": "Prediction updated",
        "id": prediction.id,
        "your_prediction": prediction.predicted_winner,
        "actual_winner": prediction.actual_winner,
        "user_correct": prediction.user_correct,
        "model_correct": prediction.model_correct,
        "verdict": (
            "🎉 You predicted correctly!"
            if prediction.user_correct
            else "❌ Incorrect prediction"
            if prediction.user_correct is False
            else "Match not yet played"
        ),
    }


@router.delete("/{prediction_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_prediction(
    prediction_id: int,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    result = await session.execute(
        select(MatchPrediction).where(
            MatchPrediction.id == prediction_id,
            MatchPrediction.user_id == current_user.id,
        )
    )
    prediction = result.scalar_one_or_none()
    if not prediction:
        raise HTTPException(status_code=404, detail="Prediction not found")

    await session.delete(prediction)
    await session.commit()
