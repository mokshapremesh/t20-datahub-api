const FLAG_MAP = {
  'India': '🇮🇳',
  'Pakistan': '🇵🇰',
  'Australia': '🇦🇺',
  'England': '🏴󠁧󠁢󠁥󠁮󠁧󠁿',
  'New Zealand': '🇳🇿',
  'South Africa': '🇿🇦',
  'West Indies': '🏝️',
  'Sri Lanka': '🇱🇰',
  'Bangladesh': '🇧🇩',
  'Afghanistan': '🇦🇫',
  'Zimbabwe': '🇿🇼',
  'Ireland': '🇮🇪',
  'Netherlands': '🇳🇱',
  'Scotland': '🏴󠁧󠁢󠁳󠁣󠁴󠁿',
  'Namibia': '🇳🇦',
  'Papua New Guinea': '🇵🇬',
  'Uganda': '🇺🇬',
  'U.S.A.': '🇺🇸',
  'USA': '🇺🇸',
  'Canada': '🇨🇦',
  'Oman': '🇴🇲',
  'Nepal': '🇳🇵',
  'Kenya': '🇰🇪',
  'Hong Kong': '🇭🇰',
  'United Arab Emirates': '🇦🇪',
  'UAE': '🇦🇪',
}

export function teamFlag(name) {
  if (!name) return ''
  return FLAG_MAP[name] ?? ''
}

export function teamWithFlag(name) {
  if (!name) return ''
  const flag = teamFlag(name)
  return flag ? `${flag} ${name}` : name
}
