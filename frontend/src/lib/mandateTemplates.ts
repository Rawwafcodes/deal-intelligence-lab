// Categorizes mandates.py's own real _TEMPLATES registry into the four
// starting structures docs/product/03 describes (Flexible/Review/
// Pipeline/Monitoring). Flexible has no template at all - it is the
// LLM-planning path (proposePlanWithAi), which picks a template on its
// own. Monitoring has no template either - it is triggers.py's own
// domain, reused via the existing Triggers page, not a mandate
// capability.
//
// "review" and "hiddenFromComposer" are frontend-only display
// decisions, not backend changes: every key in _TEMPLATES is still
// reachable via the existing manual template dropdown in
// MandateDetail.tsx regardless of this categorization. The two
// fixture-* templates are hidden from the composer specifically
// because their own registered descriptions say plainly that they
// "prove the runtime end to end" and "register no real analytical
// capability" - showing them as a real professional Pipeline option
// would misrepresent internal proof-of-concept scaffolding as a real
// workflow, the opposite failure from inventing a fake one.
export const REVIEW_TEMPLATE_KEYS = ["integrity-review"]
export const HIDDEN_FROM_COMPOSER_KEYS = ["fixture-echo", "fixture-echo-with-review"]

export function isReviewTemplate(key: string): boolean {
  return REVIEW_TEMPLATE_KEYS.includes(key)
}

export function isPipelineTemplate(key: string): boolean {
  return !REVIEW_TEMPLATE_KEYS.includes(key) && !HIDDEN_FROM_COMPOSER_KEYS.includes(key)
}
