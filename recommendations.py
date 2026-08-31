WELLNESS_RECOMMENDATIONS = {
    "Happy": [
        "Great to see you're feeling good! Take a moment to note what contributed to this — it helps to recognize your own positive patterns.",
        "Keep this momentum going: consider sharing your positive energy with a colleague or teammate today.",
    ],
    "Neutral": [
        "A calm, steady mood is a good baseline. A short 5-minute walk or stretch break can help maintain it.",
        "Nothing urgent here — this could be a good time to plan your day or check in on a personal goal.",
    ],
    "Sad": {
        "low": "It looks like there might be a touch of sadness here. Consider writing a bit more in your journal about what's on your mind.",
        "medium": "Try a short guided breathing exercise (4 seconds in, 4 seconds hold, 4 seconds out) or step outside for a few minutes.",
        "high": "This seems like a strong low mood. Please consider talking to a trusted colleague, friend, or your HR/EAP wellness contact today.",
    },
    "Stress": {
        "low": "A little stress is normal — try a quick 2-minute breathing break before your next task.",
        "medium": "Consider breaking your current task into smaller steps, and take a 10-minute break away from your screen.",
        "high": "Your stress signal looks high. Try a longer break, deep breathing, or a short walk, and consider flagging your workload to your manager or HR.",
    },
    "Angry": {
        "low": "A bit of frustration is showing. A short pause before responding to anything stressful can help.",
        "medium": "Try stepping away for 5-10 minutes before continuing. Cognitive reframing — writing down the situation objectively — can help too.",
        "high": "This reads as strong frustration or anger. Please take a proper break away from the trigger, and consider talking it through with someone you trust or your HR/EAP contact.",
    },
    "Fear": {
        "low": "A little anxiety is showing. Grounding techniques (naming 5 things you can see, 4 you can hear) can help settle it.",
        "medium": "Try a short guided breathing or grounding exercise, and write down specifically what's worrying you — it often feels more manageable on paper.",
        "high": "This looks like a strong fear/anxiety signal. Please consider reaching out to a trusted colleague, your HR/EAP program, or a mental health professional.",
    },
}

MOOD_TO_EMOTION_BUCKET = {
    "Amazing": "Happy",
    "Happy": "Happy",
    "Normal": "Neutral",
    "Sad": "Sad",
    "Angry": "Angry",
}

def _confidence_bucket(confidence: float) -> str:
    if confidence is None:
        return "medium"
    if confidence < 0.4:
        return "low"
    if confidence < 0.7:
        return "medium"
    return "high"

def get_recommendation(
    emotion_label: str,
    confidence: float = None,
    sentiment: str = None,
    sentiment_score: float = None,
) -> str:
    effective_label = emotion_label
    effective_confidence = confidence

    if emotion_label == "Neutral" and sentiment == "Negative":
        
        effective_label = "Sad"
        magnitude = abs(sentiment_score) if sentiment_score is not None else 0.3
        effective_confidence = magnitude  

    entry = WELLNESS_RECOMMENDATIONS.get(effective_label)
    if entry is None:
        return "Take a moment to check in with yourself today."

    if isinstance(entry, list):
        
        import random
        return random.choice(entry)

    bucket = _confidence_bucket(effective_confidence)
    return entry[bucket]

def get_period_recommendation(entries: list[dict]) -> str:
    if not entries:
        return "No entries were logged in this period yet."

    bucket_counts: dict[str, int] = {}
    bucket_confidences: dict[str, list[float]] = {}

    for e in entries:
        if e.get("source") == "nlp" and e.get("emotion"):
            bucket = e["emotion"]
            conf = e.get("confidence")
        else:
            bucket = MOOD_TO_EMOTION_BUCKET.get(e.get("sentiment"), "Neutral")
            conf = None

        bucket_counts[bucket] = bucket_counts.get(bucket, 0) + 1
        if conf is not None:
            bucket_confidences.setdefault(bucket, []).append(conf)

    total = sum(bucket_counts.values())
    dominant_bucket = max(bucket_counts, key=bucket_counts.get)
    dominant_count = bucket_counts[dominant_bucket]
    pct = round(100 * dominant_count / total)

    confs = bucket_confidences.get(dominant_bucket)
    avg_conf = sum(confs) / len(confs) if confs else None

    tip = get_recommendation(dominant_bucket, avg_conf)

    overview = (
        f"Over this period, {dominant_bucket.lower()} was your most common state "
        f"({dominant_count} of {total} entries, {pct}%)."
    )
    closing = "Keep logging regularly so trends like this are easier to catch early."

    return f"{overview} {tip} {closing}"

QUESTIONNAIRE_RECOMMENDATIONS = {
    "Thriving": "Your check-in looks great today. Take a moment to note what's working well so you can lean on it again later.",
    "Doing Well": "You're in a solid place overall. A short break or a few minutes of stretching can help you keep this steady.",
    "Needs Attention": "A few areas could use some care today. A proper break or a short walk could help before you push on.",
    "At Risk": "Several signals here point to a tough day. Please consider talking to a trusted colleague, your manager, or your HR/EAP wellness contact -- you don't have to carry this alone.",
}

SUPPORT_PREF_TIPS = {
    "Breathing/Relaxation Exercise": "Try a slow 4-7-8 breathing cycle for two minutes: in for 4, hold for 7, out for 8.",
    "Journaling Prompt": "Try writing for 5 minutes on: \"What's one thing weighing on me, and one thing going right?\"",
    "Motivational Content": "Remember: progress doesn't have to be dramatic today -- one small completed task counts.",
    "Cognitive Reframing": "Ask yourself: is there another way to view today's biggest stressor that feels less all-or-nothing?",
    "Mindfulness Activity": "Try a 3-minute body scan: notice your feet, then breath, then shoulders, releasing tension as you go.",
    "Professional Support Information": "Consider reaching out to your EAP (Employee Assistance Program) or a licensed counselor -- it's confidential and free for most employees.",
}

HELP_NOW_TIPS = {
    "Relaxation": "Step away for 5 minutes and do something calming -- music, stretching, or just sitting quietly.",
    "Someone to talk to": "Reach out to a colleague, friend, or your manager for even a short conversation today.",
    "Motivation": "Break your next task into one small, concrete step and start with just that.",
    "Taking a break": "Block off a proper 10-15 minute break away from your desk this afternoon.",
    "Organizing my tasks": "Spend 5 minutes listing today's tasks in priority order -- it often shrinks the overwhelm.",
    "Physical activity": "A short walk or a few minutes of movement can help reset your energy and mood.",
    "Sleep/rest": "Prioritize winding down earlier tonight -- even 30 extra minutes of sleep helps.",
    "I'm not sure": "That's okay -- sometimes just naming how you feel is a good first step.",
}

def get_questionnaire_recommendation(category: str, support_pref: str | None = None,
                                      help_now: str | None = None, wants_to_talk: str | None = None) -> dict:
    lines = [QUESTIONNAIRE_RECOMMENDATIONS.get(category, "Take a moment to check in with yourself today.")]

    support_tip = SUPPORT_PREF_TIPS.get(support_pref)
    if support_tip:
        lines.append(f"**Since you'd like {support_pref.lower()}:** {support_tip}")

    help_tip = HELP_NOW_TIPS.get(help_now)
    if help_tip:
        lines.append(f"**To help you feel better right now:** {help_tip}")

    escalate = (category == "At Risk") or (wants_to_talk == "Yes")
    if escalate:
        lines.append(
            "It looks like this might be a good moment to talk to someone -- your manager, "
            "HR, or an EAP counselor can help."
        )

    return {"message": "\n\n".join(lines), "escalate": escalate}

def get_team_recommendation(mood_rows: list, questionnaire_rows: list) -> dict:
    from collections import Counter

    stats = {}
    mood_counts = Counter(r["sentiment"] for r in mood_rows if r.get("sentiment"))
    stats["mood_counts"] = dict(mood_counts)

    emo_counts = Counter(r["emotion"] for r in mood_rows if r.get("source") == "nlp" and r.get("emotion"))
    stats["emotion_counts"] = dict(emo_counts)

    total_qn = len(questionnaire_rows)
    category_counts = Counter(r["category"] for r in questionnaire_rows)
    stats["category_counts"] = dict(category_counts)

    factor_counts = Counter()
    support_counts = Counter()
    for r in questionnaire_rows:
        ans = r.get("answers") or {}
        if ans.get("q4_main_factor"):
            factor_counts[ans["q4_main_factor"]] += 1
        if ans.get("q7_support_pref"):
            support_counts[ans["q7_support_pref"]] += 1
    stats["factor_counts"] = dict(factor_counts)
    stats["support_counts"] = dict(support_counts)

    if total_qn == 0:
        return {"message": "Not enough check-in data yet to generate a team recommendation.", "stats": stats}

    at_risk_pct = round(100 * category_counts.get("At Risk", 0) / total_qn)
    doing_well_pct = round(100 * (category_counts.get("Thriving", 0) + category_counts.get("Doing Well", 0)) / total_qn)
    wants_to_talk_count = sum(1 for r in questionnaire_rows if r.get("wants_to_talk") == "Yes")
    top_factor = factor_counts.most_common(1)[0][0] if factor_counts else None

    lines = [
        f"Across {total_qn} check-in(s) this period, {doing_well_pct}% were 'Thriving' or "
        f"'Doing Well', while {at_risk_pct}% were flagged 'At Risk'."
    ]
    if top_factor:
        lines.append(
            f"The most commonly cited factor affecting mood was **{top_factor}** -- worth "
            f"checking whether a team-wide adjustment could help."
        )
    if wants_to_talk_count > 0:
        lines.append(
            f"{wants_to_talk_count} check-in(s) indicated a wish to talk to someone. Individual "
            f"identities aren't shared here -- consider a general reminder about EAP/support "
            f"resources for the whole team rather than singling anyone out."
        )
    if at_risk_pct >= 25:
        lines.append("With a notable share of the team at risk, a lighter workload week or an "
                      "open office-hours slot could help.")

    return {"message": "\n\n".join(lines), "stats": stats}
