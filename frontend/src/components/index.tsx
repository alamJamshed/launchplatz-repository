import type {
  ButtonHTMLAttributes,
  HTMLAttributes,
  InputHTMLAttributes,
  ReactNode,
  SelectHTMLAttributes,
  TextareaHTMLAttributes,
} from 'react'
import { useEffect, useRef } from 'react'
import { Search, X } from 'lucide-react'

const cx = (...classes: Array<string | false | null | undefined>) => classes.filter(Boolean).join(' ')

export type ButtonVariant = 'primary' | 'secondary' | 'danger' | 'ghost'

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant
  size?: 'small' | 'medium'
  loading?: boolean
  icon?: ReactNode
}

export function Button({
  variant = 'primary',
  size = 'medium',
  loading = false,
  icon,
  className,
  children,
  disabled,
  ...props
}: ButtonProps) {
  return (
    <button
      className={cx('ds-button', `ds-button--${variant}`, `ds-button--${size}`, className)}
      disabled={disabled || loading}
      {...props}
    >
      {loading ? <Spinner size="small" label="" /> : icon}
      {children}
    </button>
  )
}

type FieldBase = {
  label: string
  hint?: string
  error?: string
  optional?: boolean
  id: string
}

export type TextFieldProps = FieldBase & InputHTMLAttributes<HTMLInputElement>

export function TextField({ label, hint, error, optional, id, className, ...props }: TextFieldProps) {
  const descriptionId = hint || error ? `${id}-description` : undefined
  return (
    <label className="ds-field" htmlFor={id}>
      <span className="ds-field__label">{label}{optional && <small>Optional</small>}</span>
      <input id={id} className={cx('ds-input', error && 'is-invalid', className)} aria-invalid={Boolean(error)} aria-describedby={descriptionId} {...props} />
      {(error || hint) && <span id={descriptionId} className={cx('ds-field__help', error && 'is-error')}>{error || hint}</span>}
    </label>
  )
}

export type TextAreaProps = FieldBase & TextareaHTMLAttributes<HTMLTextAreaElement>

export function TextArea({ label, hint, error, optional, id, className, ...props }: TextAreaProps) {
  const descriptionId = hint || error ? `${id}-description` : undefined
  return (
    <label className="ds-field" htmlFor={id}>
      <span className="ds-field__label">{label}{optional && <small>Optional</small>}</span>
      <textarea id={id} className={cx('ds-input ds-textarea', error && 'is-invalid', className)} aria-invalid={Boolean(error)} aria-describedby={descriptionId} {...props} />
      {(error || hint) && <span id={descriptionId} className={cx('ds-field__help', error && 'is-error')}>{error || hint}</span>}
    </label>
  )
}

export type SelectFieldProps = FieldBase & SelectHTMLAttributes<HTMLSelectElement>

export function SelectField({ label, hint, error, optional, id, className, children, ...props }: SelectFieldProps) {
  const descriptionId = hint || error ? `${id}-description` : undefined
  return (
    <label className="ds-field" htmlFor={id}>
      <span className="ds-field__label">{label}{optional && <small>Optional</small>}</span>
      <select id={id} className={cx('ds-input ds-select', error && 'is-invalid', className)} aria-invalid={Boolean(error)} aria-describedby={descriptionId} {...props}>{children}</select>
      {(error || hint) && <span id={descriptionId} className={cx('ds-field__help', error && 'is-error')}>{error || hint}</span>}
    </label>
  )
}

export interface SearchFieldProps extends Omit<InputHTMLAttributes<HTMLInputElement>, 'type'> {
  label?: string
}

export function SearchField({ label = 'Search', className, ...props }: SearchFieldProps) {
  return (
    <label className={cx('ds-search', className)}>
      <span className="sr-only">{label}</span>
      <Search aria-hidden="true" size={17} />
      <input type="search" className="ds-input" {...props} />
    </label>
  )
}

export function Card({ className, ...props }: HTMLAttributes<HTMLElement>) {
  return <section className={cx('ds-card', className)} {...props} />
}

export type BadgeTone = 'neutral' | 'success' | 'warning' | 'danger' | 'info'

export function Badge({ tone = 'neutral', className, ...props }: HTMLAttributes<HTMLSpanElement> & { tone?: BadgeTone }) {
  return <span className={cx('ds-badge', `ds-badge--${tone}`, className)} {...props} />
}

export function Alert({ tone = 'info', title, children }: { tone?: BadgeTone; title?: string; children: ReactNode }) {
  return <div className={cx('ds-alert', `ds-alert--${tone}`)} role={tone === 'danger' ? 'alert' : 'status'}>{title && <strong>{title}</strong>}<span>{children}</span></div>
}

export function Avatar({ name, size = 'medium' }: { name: string; size?: 'small' | 'medium' | 'large' }) {
  const initials = name.split(/\s+/).slice(0, 2).map((part) => part[0]).join('').toUpperCase()
  return <span className={cx('ds-avatar', `ds-avatar--${size}`)} aria-label={name}>{initials}</span>
}

export function Spinner({ size = 'medium', label = 'Loading' }: { size?: 'small' | 'medium' | 'large'; label?: string }) {
  return <span className={cx('ds-spinner', `ds-spinner--${size}`)} role={label ? 'status' : undefined}><span aria-hidden="true" />{label && <span className="sr-only">{label}</span>}</span>
}

export function EmptyState({ icon, title, description, action }: { icon?: ReactNode; title: string; description: string; action?: ReactNode }) {
  return <div className="ds-empty">{icon && <span className="ds-empty__icon">{icon}</span>}<h3>{title}</h3><p>{description}</p>{action}</div>
}

export function PageHeading({ title, description, action }: { title: string; description?: string; action?: ReactNode }) {
  return <header className="ds-page-heading"><div><h1>{title}</h1>{description && <p>{description}</p>}</div>{action}</header>
}

export type TableColumn<Row> = {
  key: string
  heading: string
  render: (row: Row) => ReactNode
  className?: string
}

export function DataTable<Row>({ columns, rows, rowKey, caption }: { columns: TableColumn<Row>[]; rows: Row[]; rowKey: (row: Row) => string; caption: string }) {
  return (
    <div className="ds-table-wrap">
      <table className="ds-table">
        <caption className="sr-only">{caption}</caption>
        <thead><tr>{columns.map((column) => <th className={column.className} key={column.key} scope="col">{column.heading}</th>)}</tr></thead>
        <tbody>{rows.map((row) => <tr key={rowKey(row)}>{columns.map((column) => <td className={column.className} key={column.key}>{column.render(row)}</td>)}</tr>)}</tbody>
      </table>
    </div>
  )
}

export interface ModalProps {
  open: boolean
  title: string
  description?: string
  children: ReactNode
  footer?: ReactNode
  onClose: () => void
}

export function Modal({ open, title, description, children, footer, onClose }: ModalProps) {
  const dialogRef = useRef<HTMLElement>(null)
  const onCloseRef = useRef(onClose)
  useEffect(() => {
    onCloseRef.current = onClose
  }, [onClose])
  useEffect(() => {
    if (!open) return
    const previous = document.activeElement as HTMLElement | null
    const dialog = dialogRef.current
    const focusable = dialog?.querySelector<HTMLElement>(
      '.ds-modal__body input, .ds-modal__body textarea, .ds-modal__body select, .ds-modal__body button, button',
    )
    focusable?.focus()
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onCloseRef.current()
      if (event.key !== 'Tab' || !dialog) return
      const elements = Array.from(dialog.querySelectorAll<HTMLElement>('button, input, textarea, select, [tabindex]:not([tabindex="-1"])')).filter((element) => !element.hasAttribute('disabled'))
      if (!elements.length) return
      const first = elements[0]
      const last = elements[elements.length - 1]
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus() }
      if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus() }
    }
    document.addEventListener('keydown', onKeyDown)
    return () => { document.removeEventListener('keydown', onKeyDown); previous?.focus() }
  }, [open])
  if (!open) return null
  return (
    <div className="ds-modal-backdrop" role="presentation" onMouseDown={(event) => event.target === event.currentTarget && onClose()}>
      <section ref={dialogRef} className="ds-modal" role="dialog" aria-modal="true" aria-labelledby="modal-title">
        <header className="ds-modal__header"><div><h2 id="modal-title">{title}</h2>{description && <p>{description}</p>}</div><button className="ds-icon-button" type="button" aria-label="Close dialog" onClick={onClose}><X size={18} /></button></header>
        <div className="ds-modal__body">{children}</div>
        {footer && <footer className="ds-modal__footer">{footer}</footer>}
      </section>
    </div>
  )
}

export function ConfirmModal({ open, title, description, confirmLabel = 'Confirm', danger = false, loading = false, onConfirm, onClose }: { open: boolean; title: string; description: string; confirmLabel?: string; danger?: boolean; loading?: boolean; onConfirm: () => void; onClose: () => void }) {
  return <Modal open={open} title={title} description={description} onClose={onClose} footer={<><Button variant="secondary" onClick={onClose}>Cancel</Button><Button variant={danger ? 'danger' : 'primary'} loading={loading} onClick={onConfirm}>{confirmLabel}</Button></>}><p className="ds-confirm-copy">This action will be applied immediately.</p></Modal>
}

export function Pagination({ count, limit, offset, onChange }: { count: number; limit: number; offset: number; onChange: (offset: number) => void }) {
  const start = count ? offset + 1 : 0
  const end = Math.min(count, offset + limit)
  return <div className="ds-pagination"><span>{start}-{end} of {count}</span><div><Button size="small" variant="secondary" disabled={offset === 0} onClick={() => onChange(Math.max(0, offset - limit))}>Previous</Button><Button size="small" variant="secondary" disabled={offset + limit >= count} onClick={() => onChange(offset + limit)}>Next</Button></div></div>
}

export function Skeleton({ lines = 3 }: { lines?: number }) {
  return <div className="ds-skeleton" aria-label="Loading">{Array.from({ length: lines }, (_, index) => <span key={index} />)}</div>
}

export interface NavItem {
  id: string
  label: string
  icon?: ReactNode
  badge?: string
}

export function SideNav({ items, activeId, onChange, label = 'Primary navigation' }: { items: NavItem[]; activeId: string; onChange: (id: string) => void; label?: string }) {
  return <nav className="ds-side-nav" aria-label={label}>{items.map((item) => <button className={item.id === activeId ? 'active' : ''} type="button" key={item.id} aria-current={item.id === activeId ? 'page' : undefined} onClick={() => onChange(item.id)}>{item.icon}<span>{item.label}</span>{item.badge && <Badge tone="warning">{item.badge}</Badge>}</button>)}</nav>
}

export function AuthLayout({ title, description, children, footer }: { title: string; description: string; children: ReactNode; footer?: ReactNode }) {
  return <main className="ds-auth"><section className="ds-auth__card"><div className="ds-brand-mark" aria-hidden="true">L</div><header><h1>{title}</h1><p>{description}</p></header>{children}{footer && <footer>{footer}</footer>}</section></main>
}

export function DashboardLayout({ brand = 'LaunchPlatz', userName, nav, activeId, onNavigate, onLogout, children }: { brand?: string; userName: string; nav: NavItem[]; activeId: string; onNavigate: (id: string) => void; onLogout?: () => void; children: ReactNode }) {
  return <div className="ds-dashboard"><header className="ds-topbar"><a className="ds-brand" href="#gallery" aria-label={`${brand} home`}><span aria-hidden="true">L</span>{brand}</a><div className="ds-user"><Avatar name={userName} size="small" /><span>{userName}</span>{onLogout && <Button variant="ghost" size="small" onClick={onLogout}>Log out</Button>}</div></header><div className="ds-shell"><aside><SideNav items={nav} activeId={activeId} onChange={onNavigate} /></aside><main className="ds-content">{children}</main></div></div>
}
