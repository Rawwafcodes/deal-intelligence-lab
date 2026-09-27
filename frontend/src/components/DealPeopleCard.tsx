import { useEffect, useState } from "react"
import { Link } from "react-router-dom"
import { toast } from "sonner"

import { Button } from "@/components/ui/button"
import { Card } from "@/components/ui/card"
import {
  DEAL_ROLES,
  getOrganization,
  grantDealAccess,
  listDealMembers,
  revokeDealAccess,
  type DealMembershipWithUser,
  type OrganizationDetails,
} from "@/lib/api"
import { useCapability } from "@/lib/dealAccess"

// Task 19.5 (M19, surface #23 at deal level): who has access to this deal and
// in what role. Only the deal lead (manage_membership) can add or remove, and
// only people already in the organization (the server enforces both).

const ROLE_LABELS: Record<string, string> = {
  deal_lead: "Deal lead", reviewer: "Reviewer", analyst: "Analyst", external_executive: "External executive",
}
const SELECT_CLASS = "rounded-md border border-border bg-background px-2 py-1.5 text-sm text-foreground"

export function DealPeopleCard({ projectId }: { projectId: string }) {
  const canManage = useCapability("manage_membership")
  const [members, setMembers] = useState<DealMembershipWithUser[] | null>(null)
  const [org, setOrg] = useState<OrganizationDetails | null>(null)
  const [userId, setUserId] = useState("")
  const [role, setRole] = useState<string>("analyst")
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    listDealMembers(projectId).then(setMembers).catch(() => setMembers([]))
    if (canManage) getOrganization().then(setOrg).catch(() => setOrg(null))
  }, [projectId, canManage])

  const active = (members ?? []).filter((m) => !m.revoked_at)
  const activeIds = new Set(active.map((m) => m.user_id))
  const candidates = (org?.members ?? []).filter((m) => !activeIds.has(m.user.id))

  async function add() {
    if (!userId) return
    setBusy(true)
    try {
      setMembers(await grantDealAccess(projectId, userId, role))
      setUserId("")
      toast.success("Access granted.")
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Could not give this person access.")
    } finally {
      setBusy(false)
    }
  }

  async function remove(member: DealMembershipWithUser) {
    setBusy(true)
    try {
      await revokeDealAccess(projectId, member.user_id)
      setMembers(await listDealMembers(projectId))
      toast.success(`${member.user?.display_name ?? "This person"} no longer has access.`)
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Could not remove this person's access.")
    } finally {
      setBusy(false)
    }
  }

  return (
    <Card className="p-6">
      <h2 className="font-heading text-lg font-semibold text-foreground">People on this deal</h2>
      {members === null ? (
        <p className="mt-2 text-sm text-muted-foreground">Loading…</p>
      ) : (
        <ul className="mt-3 divide-y divide-border">
          {active.map((member) => (
            <li key={member.id} className="flex flex-wrap items-center justify-between gap-2 py-2 text-sm">
              <span className="min-w-0 text-foreground">
                {member.user?.display_name ?? "Unknown"}{" "}
                <span className="text-xs text-muted-foreground">{member.user?.email}</span>
              </span>
              <span className="flex items-center gap-3">
                <span className="text-xs text-muted-foreground">{ROLE_LABELS[member.role] ?? member.role}</span>
                {canManage && (
                  <Button size="sm" variant="secondary" disabled={busy} onClick={() => remove(member)}>
                    Remove
                  </Button>
                )}
              </span>
            </li>
          ))}
        </ul>
      )}
      {canManage && (
        <div className="mt-4 flex flex-wrap items-end gap-2">
          <label className="grid gap-1 text-xs font-medium text-muted-foreground">
            Person
            <select aria-label="Person to add" className={SELECT_CLASS} value={userId} onChange={(e) => setUserId(e.target.value)}>
              <option value="">{candidates.length ? "Choose someone…" : "Everyone in the organization is on this deal"}</option>
              {candidates.map((m) => (
                <option key={m.user.id} value={m.user.id}>{m.user.display_name} ({m.user.email})</option>
              ))}
            </select>
          </label>
          <label className="grid gap-1 text-xs font-medium text-muted-foreground">
            Role
            <select aria-label="Deal role" className={SELECT_CLASS} value={role} onChange={(e) => setRole(e.target.value)}>
              {DEAL_ROLES.map((r) => <option key={r} value={r}>{ROLE_LABELS[r]}</option>)}
            </select>
          </label>
          <Button size="sm" disabled={busy || !userId} onClick={add}>Add to deal</Button>
          <Link to="/team" className="text-xs text-muted-foreground underline">Invite someone new</Link>
        </div>
      )}
    </Card>
  )
}
