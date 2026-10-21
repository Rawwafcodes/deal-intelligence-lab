import { useEffect, useState } from "react"
import { toast } from "sonner"

import { Button } from "@/components/ui/button"
import { Card } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import {
  DEAL_PARTY_ROLES,
  inviteDealPartyContact,
  listDealParties,
  removeDealParty,
  type DealParty,
} from "@/lib/api"
import { useCapability } from "@/lib/dealAccess"

// Task 20.1-20.3 (Path B: multi-firm-per-deal): organizations other than
// this deal's own owner, given deal access - the counterparty's team,
// their legal counsel, a lender. Their members are always restricted to
// the external_executive role (Task 20.2); giving a specific party access
// to a specific document beyond that default happens from the Documents
// page, not here. See docs/workspace-shift/tasks/path-b-multi-firm-
// architecture-decision-report.md.

const PARTY_ROLE_LABELS: Record<string, string> = {
  counterparty: "Counterparty", legal_counsel: "Legal counsel", lender: "Lender", other: "Other",
}
const SELECT_CLASS = "rounded-md border border-border bg-background px-2 py-1.5 text-sm text-foreground"

export function DealPartiesCard({ projectId }: { projectId: string }) {
  const canManage = useCapability("manage_deal_parties")
  const [parties, setParties] = useState<DealParty[] | null>(null)
  const [email, setEmail] = useState("")
  const [displayName, setDisplayName] = useState("")
  const [organizationName, setOrganizationName] = useState("")
  const [partyRole, setPartyRole] = useState<string>("counterparty")
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    if (canManage) listDealParties(projectId).then(setParties).catch(() => setParties([]))
  }, [projectId, canManage])

  if (!canManage) return null

  async function invite(event: React.FormEvent) {
    event.preventDefault()
    if (!email.trim() || !organizationName.trim()) return
    setBusy(true)
    try {
      const result = await inviteDealPartyContact(projectId, {
        partyRole, email: email.trim(), displayName: displayName.trim(), organizationName: organizationName.trim(),
      })
      setParties(await listDealParties(projectId))
      setEmail("")
      setDisplayName("")
      setOrganizationName("")
      setPartyRole("counterparty")
      toast.success(`${result.organization.name} now has access to this deal, as ${result.user.display_name || result.user.email}.`)
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Could not invite this outside contact.")
    } finally {
      setBusy(false)
    }
  }

  async function remove(party: DealParty) {
    setBusy(true)
    try {
      await removeDealParty(projectId, party.organization_id)
      setParties(await listDealParties(projectId))
      toast.success(`${party.organization?.name ?? "That organization"} no longer has access to this deal.`)
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Could not remove this party.")
    } finally {
      setBusy(false)
    }
  }

  return (
    <Card className="p-6">
      <h2 className="font-heading text-lg font-semibold text-foreground">Other organizations on this deal</h2>
      <p className="mt-1 text-sm text-muted-foreground">
        A counterparty, their legal counsel, a lender. Their people get a restricted view by default - your own documents,
        findings and work stay internal unless you share a specific document with them.
      </p>

      {parties === null ? (
        <p className="mt-3 text-sm text-muted-foreground">Loading…</p>
      ) : parties.length === 0 ? (
        <p className="mt-3 text-sm text-muted-foreground">No other organizations have access yet.</p>
      ) : (
        <ul className="mt-3 divide-y divide-border">
          {parties.map((party) => (
            <li key={party.id} className="flex flex-wrap items-center justify-between gap-2 py-2 text-sm">
              <span className="min-w-0 text-foreground">
                {party.organization?.name ?? "Unknown organization"}{" "}
                <span className="text-xs text-muted-foreground">{PARTY_ROLE_LABELS[party.party_role] ?? party.party_role}</span>
              </span>
              <Button size="sm" variant="secondary" disabled={busy} onClick={() => remove(party)}>Remove</Button>
            </li>
          ))}
        </ul>
      )}

      <form onSubmit={invite} className="mt-4 grid gap-3 sm:grid-cols-2">
        <label className="grid gap-1 text-xs font-medium text-muted-foreground">
          Their organization
          <Input placeholder="Acme Capital LLP" value={organizationName} onChange={(e) => setOrganizationName(e.target.value)} />
        </label>
        <label className="grid gap-1 text-xs font-medium text-muted-foreground">
          Relationship
          <select aria-label="Party role" className={SELECT_CLASS} value={partyRole} onChange={(e) => setPartyRole(e.target.value)}>
            {DEAL_PARTY_ROLES.map((r) => <option key={r} value={r}>{PARTY_ROLE_LABELS[r]}</option>)}
          </select>
        </label>
        <label className="grid gap-1 text-xs font-medium text-muted-foreground">
          Their contact&rsquo;s email
          <Input type="email" placeholder="name@theirfirm.com" value={email} onChange={(e) => setEmail(e.target.value)} />
        </label>
        <label className="grid gap-1 text-xs font-medium text-muted-foreground">
          Their name
          <Input value={displayName} onChange={(e) => setDisplayName(e.target.value)} />
        </label>
        <Button type="submit" className="sm:col-span-2 sm:w-fit" disabled={busy || !email.trim() || !organizationName.trim()}>
          Give them access
        </Button>
      </form>
    </Card>
  )
}
