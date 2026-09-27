import { UserButton } from "@clerk/react"

// Task 19.4 (M19): Clerk's account menu, lazily loaded by IdentityFooter
// only in hosted mode.
export default function HostedUserButton() {
  return <UserButton />
}
