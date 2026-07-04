PLUGIN_NAME = "idea-spark"
TOOLSET = "idea_spark"
PROTOCOL = "idea_spark_ml_review_v1"

TOOL_NAMES = [
    "idea_spark_room_create",
    "idea_spark_room_join",
    "idea_spark_room_status",
    "idea_spark_message_post",
    "idea_spark_message_read",
    "idea_spark_round_wait",
    "idea_spark_artifact_create",
    "idea_spark_artifact_read",
    "idea_spark_artifact_link",
    "idea_spark_artifact_status_update",
    "idea_spark_gate_record",
    "idea_spark_need_create",
    "idea_spark_need_update",
    "idea_spark_room_export",
]

ARTIFACT_TYPES = {
    "ResearchGoal",
    "IdeaCard",
    "EvaluationRubric",
    "AtomicClaim",
    "Assumption",
    "PriorArtEvidence",
    "EvidenceLink",
    "NoveltyObjection",
    "FeasibilityObjection",
    "ReviewerRisk",
    "Rebuttal",
    "RevisionPlan",
    "ExperimentPlan",
    "StressTest",
    "BenchmarkRequirement",
    "ScoreCard",
    "GateDecision",
    "OpenNeed",
    "RegimeTransition",
    "MetaReview",
}

ARTIFACT_STATUSES = {"proposed", "accepted", "rejected", "superseded", "retracted", "stale"}
GATE_DECISIONS = {"accepted", "rejected", "superseded", "retracted", "needs_more_evidence"}
RELATIONS = {
    "supports",
    "contradicts",
    "critiques",
    "rebuts",
    "supersedes",
    "evolves_from",
    "requires",
    "assumes",
    "cites",
    "compares_against",
    "fails_under",
    "passes_gate",
    "rejected_by_gate",
    "introduced_by_transition",
    "transported_from_prior_schema",
    "decomposes",
}
