import { type ReactNode, useEffect, useState } from "react"
import { Show, SignIn, UserButton } from "@clerk/react"

import { Card } from "@/components/ui/card"

// Task 19.4 (M19): hosted-mode entry. Signed out -> the sign-in screen.
// Signed in -> confirm with the server that this account has been invited
// (sign-in proves identity; access is invite-only, decided server-side)
// before rendering the app, so an uninvited account sees one clear message
// instead of every page failing.

function Centered({ children }: { children: ReactNode }) {
  return <div className="flex min-h-svh items-center justify-center bg-background px-4 py-10">{children}</div>
}

function InvitationCheck({ children }: { children: ReactNode }) {
  const [state, setState] = useState<"checking" | "ok" | "not_invited" | "error">("checking")

  useEffect(() => {
    let cancelled = false
    async function check(attempt: number) {
      const res = await fetch("/api/session").catch(() => null)
      if (cancelled) return
      if (res?.ok) return setState("ok")
      if (res?.status === 403) return setState("not_invited")
      // Right after sign-in the session cookie can land a moment later.
      if (res?.status === 401 && attempt < 3) return void setTimeout(() => check(attempt + 1), 500)
      setState("error")
    }
    check(0)
    return () => {
      cancelled = true
    }
  }, [])

  if (state === "ok") return <>{children}</>
  if (state === "checking") {
    return <Centered><p className="text-sm text-muted-foreground">Signing in…</p></Centered>
  }
  return (
    <Centered>
      <Card className="max-w-md space-y-3 p-6 text-sm">
        <h1 className="font-heading text-lg font-semibold text-foreground">
          {state === "not_invited" ? "This account hasn't been invited" : "We couldn't start your session"}
        </h1>
        <p className="text-muted-foreground">
          {state === "not_invited"
            ? "You're signed in, but this email address isn't on the workspace's invitation list. Ask the person who runs the workspace to invite you, or sign out and use the invited address."
            : "Sign-in succeeded but the workspace didn't accept the session. Try again in a moment, or sign out and back in."}
        </p>
        <div className="flex items-center gap-2 text-muted-foreground">
          <UserButton />
          <span>Account menu (sign out)</span>
        </div>
      </Card>
    </Centered>
  )
}

export function AuthGate({ children }: { children: ReactNode }) {
  return (
    <>
      <Show when="signed-out">
        <Centered>
          <div className="space-y-4 text-center">
            <p className="font-heading text-lg font-semibold text-foreground">Deal Intelligence Lab</p>
            <SignIn routing="hash" />
          </div>
        </Centered>
      </Show>
      <Show when="signed-in">
        <InvitationCheck>{children}</InvitationCheck>
      </Show>
    </>
  )
}
