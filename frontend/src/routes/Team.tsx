import { useEffect, useState } from "react"
import { toast } from "sonner"

import { Button } from "@/components/ui/button"
import { Card } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { getOrganization, inviteMember, renameOrganization, type OrganizationDetails } from "@/lib/api"
import { HOSTED_AUTH } from "@/lib/auth"

// Task 19.5 (M19): the minimal Team and Access / Organization Settings
// surfaces (#23-24) needed to run a private pilot - see who is in the
// organization, invite someone by email, rename the organization. Admin
// actions are enforced server-side; the controls are simply hidden for
// members. Deal-level access lives on each deal's overview.

const SELECT_CLASS = "rounded-md border border-border bg-background px-2 py-2 text-sm text-foreground"

export function Team() {
  const [org, setOrg] = useState<OrganizationDetails | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [name, setName] = useState("")
  const [email, setEmail] = useState("")
  const [displayName, setDisplayName] = useState("")
  const [role, setRole] = useState("member")
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    getOrganization()
      .then((details) => {
        setOrg(details)
        setName(details.organization?.name ?? "")
      })
      .catch((err) => setError(err instanceof Error ? err.message : "Could not load your organization."))
  }, [])

  const isAdmin = org?.role === "admin"

  async function run(action: () => Promise<OrganizationDetails>, success: string) {
    setBusy(true)
    try {
      const details = await action()
      setOrg(details)
      toast.success(success)
      return true
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Something went wrong.")
      return false
    } finally {
      setBusy(false)
    }
  }

  async function invite(event: React.FormEvent) {
    event.preventDefault()
    if (await run(() => inviteMember(email, displayName, role), `${email} can now sign in.`)) {
      setEmail("")
      setDisplayName("")
      setRole("member")
    }
  }

  if (error) {
    return <div className="mx-auto max-w-3xl px-6 pt-8 pb-20"><Card className="p-6 text-sm text-muted-foreground">{error}</Card></div>
  }
  if (!org) {
    return <div className="mx-auto max-w-3xl px-6 pt-8 pb-20 text-sm text-muted-foreground">Loading…</div>
  }

  return (
    <div className="mx-auto max-w-3xl space-y-4 px-6 pt-8 pb-20">
      <div>
        <h1 className="font-heading text-2xl font-semibold text-foreground">Team</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          People in {org.organization?.name ?? "your organization"}. Give someone access to a specific deal from that deal&rsquo;s overview.
        </p>
      </div>

      <Card className="p-0">
        <h2 className="border-b border-border px-4 py-3 text-sm font-semibold text-foreground">Members ({org.members.length})</h2>
        <ul className="divide-y divide-border">
          {org.members.map(({ user, role: memberRole }) => (
            <li key={user.id} className="flex flex-wrap items-center justify-between gap-2 px-4 py-2 text-sm">
              <span className="text-foreground">{user.display_name} <span className="text-xs text-muted-foreground">{user.email}</span></span>
              <span className="text-xs text-muted-foreground">{memberRole === "admin" ? "Admin" : "Member"}</span>
            </li>
          ))}
        </ul>
      </Card>

      {isAdmin && (
        <Card className="p-6">
          <h2 className="font-heading text-lg font-semibold text-foreground">Invite someone</h2>
          <p className="mt-1 text-sm text-muted-foreground">
            {HOSTED_AUTH
              ? "They sign in with this exact email address; nobody else can join."
              : "Adds them to the organization so they can be given deal access."}
          </p>
          <form onSubmit={invite} className="mt-4 grid gap-3 sm:grid-cols-[1fr_1fr_auto_auto] sm:items-end">
            <label className="grid gap-1 text-xs font-medium text-muted-foreground">
              Email
              <Input type="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
            </label>
            <label className="grid gap-1 text-xs font-medium text-muted-foreground">
              Name
              <Input value={displayName} onChange={(e) => setDisplayName(e.target.value)} />
            </label>
            <label className="grid gap-1 text-xs font-medium text-muted-foreground">
              Role
              <select aria-label="Organization role" className={SELECT_CLASS} value={role} onChange={(e) => setRole(e.target.value)}>
                <option value="member">Member</option>
                <option value="admin">Admin</option>
              </select>
            </label>
            <Button type="submit" disabled={busy || !email}>Invite</Button>
          </form>
        </Card>
      )}

      {isAdmin && (
        <Card className="p-6">
          <h2 className="font-heading text-lg font-semibold text-foreground">Organization settings</h2>
          <form
            onSubmit={(e) => { e.preventDefault(); run(() => renameOrganization(name), "Organization renamed.") }}
            className="mt-4 flex flex-wrap items-end gap-2"
          >
            <label className="grid min-w-64 flex-1 gap-1 text-xs font-medium text-muted-foreground">
              Organization name
              <Input value={name} maxLength={200} onChange={(e) => setName(e.target.value)} />
            </label>
            <Button type="submit" variant="secondary" disabled={busy || !name.trim() || name === org.organization?.name}>Save</Button>
          </form>
        </Card>
      )}
    </div>
  )
}
