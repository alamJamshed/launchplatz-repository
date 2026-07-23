import { useMemo, useState } from 'react'
import { KeyRound, Plus, RefreshCw } from 'lucide-react'
import {
  Button, ConfirmModal, DataTable, Modal, PageHeading, Pagination,
  SearchField, TextArea, TextField, type TableColumn,
} from '../components'
import { api, ApiError, type Paginated } from '../lib/api'
import { fieldErrors, formatDate } from '../lib/format'
import { useResource } from '../hooks/useResource'
import type { ServerRecord } from '../types'
import { Notice, RequestState, StatusBadge } from './shared'

type ServerForm = {
  name: string
  ip_address: string
  ssh_port: string
  username: string
  private_key: string
  generate_key: boolean
}
type CreatedServer = ServerRecord & { public_key?: string }
const emptyForm: ServerForm = {
  name: '', ip_address: '', ssh_port: '22', username: 'root',
  private_key: '', generate_key: true,
}

export function ServersPage() {
  const [offset, setOffset] = useState(0)
  const [search, setSearch] = useState('')
  const [editing, setEditing] = useState<ServerRecord | null>(null)
  const [formOpen, setFormOpen] = useState(false)
  const [form, setForm] = useState(emptyForm)
  const [errors, setErrors] = useState<Record<string, string>>({})
  const [busy, setBusy] = useState(false)
  const [deleting, setDeleting] = useState<ServerRecord | null>(null)
  const [generatedKey, setGeneratedKey] = useState<{ server: ServerRecord; publicKey: string } | null>(null)
  const [notice, setNotice] = useState<{ tone: 'success' | 'danger' | 'info'; message: string } | null>(null)
  const limit = 30
  const resource = useResource<Paginated<ServerRecord>>(
    (signal) => api.get(`/servers/?limit=${limit}&offset=${offset}`, signal),
    [offset],
  )
  const rows = useMemo(
    () => (resource.data?.results || []).filter((server) =>
      `${server.name} ${server.ip_address} ${server.username}`.toLowerCase().includes(search.toLowerCase())),
    [resource.data, search],
  )

  const openForm = (server?: ServerRecord) => {
    setEditing(server || null)
    setErrors({})
    setForm(server ? {
      name: server.name, ip_address: server.ip_address,
      ssh_port: String(server.ssh_port), username: server.username,
      private_key: '', generate_key: false,
    } : emptyForm)
    setFormOpen(true)
  }

  const submit = async (event: React.FormEvent) => {
    event.preventDefault()
    setBusy(true)
    setErrors({})
    const payload = {
      ...form,
      ssh_port: Number(form.ssh_port),
      ...(form.private_key ? {} : { private_key: undefined }),
      ...(editing ? { generate_key: undefined } : {}),
    }
    try {
      let created: CreatedServer | null = null
      if (editing) await api.patch(`/servers/${editing.id}/`, payload)
      else created = await api.post<CreatedServer>('/servers/', payload)
      setFormOpen(false)
      if (created?.public_key) {
        setGeneratedKey({ server: created, publicKey: created.public_key })
      }
      setNotice({ tone: 'success', message: `Server ${editing ? 'updated' : 'created'}.` })
      await resource.refetch()
    } catch (reason) {
      setErrors(fieldErrors((reason as ApiError).errors))
      setNotice({ tone: 'danger', message: (reason as Error).message })
    } finally {
      setBusy(false)
    }
  }

  const test = async (server: ServerRecord) => {
    setNotice({ tone: 'info', message: `Testing ${server.name}…` })
    try {
      const result = await api.post<{ status: string; reason?: string }>(
        `/servers/${server.id}/test-connection/`,
      )
      setNotice({
        tone: result.status === 'Online' ? 'success' : 'danger',
        message: `${server.name}: ${result.status}${result.reason ? ` (${result.reason})` : ''}`,
      })
      await resource.refetch()
    } catch (reason) {
      setNotice({ tone: 'danger', message: (reason as Error).message })
    }
  }

  const remove = async () => {
    if (!deleting) return
    setBusy(true)
    try {
      await api.delete(`/servers/${deleting.id}/`)
      setDeleting(null)
      setNotice({ tone: 'success', message: 'Server removed.' })
      await resource.refetch()
    } catch (reason) {
      setNotice({ tone: 'danger', message: (reason as Error).message })
    } finally {
      setBusy(false)
    }
  }

  const columns: TableColumn<ServerRecord>[] = [
    { key: 'name', heading: 'Server', render: (row) =>
      <button className="app-link-button" onClick={() => openForm(row)}>
        <strong>{row.name}</strong>
        <small>{row.username}@{row.ip_address}:{row.ssh_port}</small>
      </button> },
    { key: 'status', heading: 'Status', render: (row) => <StatusBadge status={row.status} /> },
    { key: 'checked', heading: 'Last checked', render: (row) => formatDate(row.last_checked_at) },
    { key: 'actions', heading: 'Actions', render: (row) =>
      <div className="app-row-actions">
        <Button size="small" variant="secondary" icon={<RefreshCw size={14} />} onClick={() => void test(row)}>Test</Button>
        <Button size="small" variant="danger" onClick={() => setDeleting(row)}>Delete</Button>
      </div> },
  ]

  return <>
    <PageHeading
      title="Servers"
      description="Manage VPS connections and SSH credentials."
      action={<Button icon={<Plus size={16} />} onClick={() => openForm()}>Add server</Button>}
    />
    <Notice value={notice} />
    <div className="app-toolbar">
      <SearchField value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Filter this page…" />
    </div>
    <RequestState loading={resource.loading} error={resource.error} empty={!rows.length}>
      <DataTable caption="Servers" columns={columns} rows={rows} rowKey={(row) => String(row.id)} />
      {resource.data && <Pagination count={resource.data.count} limit={limit} offset={offset} onChange={setOffset} />}
    </RequestState>

    <Modal
      open={formOpen}
      title={editing ? 'Edit server' : 'Add server'}
      description="Generate a dedicated SSH credential or use an existing private key."
      onClose={() => setFormOpen(false)}
      footer={<>
        <Button variant="secondary" onClick={() => setFormOpen(false)}>Cancel</Button>
        <Button loading={busy} onClick={() => document.getElementById('server-form-submit')?.click()}>
          {editing ? 'Save' : 'Add server'}
        </Button>
      </>}
    >
      <form className="gallery-form" onSubmit={submit}>
        <TextField id="server-name" label="Name" value={form.name} error={errors.name} onChange={(event) => setForm({ ...form, name: event.target.value })} required />
        <div className="gallery-form-grid">
          <TextField id="server-ip" label="IP address" value={form.ip_address} error={errors.ip_address} onChange={(event) => setForm({ ...form, ip_address: event.target.value })} required />
          <TextField id="server-port" label="SSH port" type="number" min="1" max="65535" value={form.ssh_port} error={errors.ssh_port} onChange={(event) => setForm({ ...form, ssh_port: event.target.value })} required />
        </div>
        <TextField id="server-user" label="Username" value={form.username} error={errors.username} onChange={(event) => setForm({ ...form, username: event.target.value })} required />
        {!editing && <label className="app-checkbox">
          <input
            type="checkbox"
            checked={form.generate_key}
            onChange={(event) => setForm({ ...form, generate_key: event.target.checked, private_key: '' })}
          />
          Generate a dedicated Ed25519 SSH key
        </label>}
        {!form.generate_key && <TextArea
          id="server-key"
          label="Private key"
          optional={Boolean(editing)}
          hint={editing ? 'Leave blank to keep the current key.' : 'Paste the complete private key.'}
          error={errors.private_key}
          value={form.private_key}
          onChange={(event) => setForm({ ...form, private_key: event.target.value })}
          required={!editing}
        />}
        <button id="server-form-submit" hidden type="submit"><KeyRound /></button>
      </form>
    </Modal>

    <Modal
      open={Boolean(generatedKey)}
      title="Install the public key"
      description={`Copy this one-time public key to ${generatedKey?.server.username}@${generatedKey?.server.ip_address}, then test the connection.`}
      onClose={() => setGeneratedKey(null)}
      footer={<>
        <Button variant="secondary" onClick={() => generatedKey && void navigator.clipboard.writeText(generatedKey.publicKey)}>Copy public key</Button>
        <Button onClick={() => setGeneratedKey(null)}>Done</Button>
      </>}
    >
      <ol>
        <li>Connect using the VPS console, password, or existing SSH access.</li>
        <li>Add this key as a new line in <code>~/.ssh/authorized_keys</code> for the selected user.</li>
        <li>Return to LaunchPlatz and click <strong>Test</strong>.</li>
      </ol>
      <pre className="app-public-key">{generatedKey?.publicKey}</pre>
      <p>The private key is encrypted inside LaunchPlatz and is never displayed.</p>
    </Modal>

    <ConfirmModal
      open={Boolean(deleting)}
      title="Delete server?"
      description={`Soft-delete ${deleting?.name || 'this server'}. Existing project references are preserved.`}
      confirmLabel="Delete server"
      danger
      loading={busy}
      onClose={() => setDeleting(null)}
      onConfirm={() => void remove()}
    />
  </>
}
