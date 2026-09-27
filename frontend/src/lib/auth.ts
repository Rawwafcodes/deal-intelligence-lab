// Task 19.4 (M19): hosted sign-in is on only when the build was given a
// Clerk publishable key (VITE_CLERK_PUBLISHABLE_KEY). Local builds leave it
// unset and keep the dev identity switcher, unchanged.
export const CLERK_PUBLISHABLE_KEY = import.meta.env.VITE_CLERK_PUBLISHABLE_KEY?.trim() || undefined
export const HOSTED_AUTH = Boolean(CLERK_PUBLISHABLE_KEY)
