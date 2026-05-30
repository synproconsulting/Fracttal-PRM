import { useCallback, useEffect, useState } from 'react'
import { formatCurrency as fmtMoney, CURRENCY_SYMBOL } from '../utils/currency.js'
import DocumentTypeSelect from '../components/DocumentTypeSelect.jsx'

const API = (typeof import.meta !== 'undefined' && import.meta.env && import.meta.env.VITE_API_URL)
  || 'https://fracttal-prm-backend-production.up.railway.app'

const STATUS_TONE = {
  draft: 'fp-badge--neutral',
  sent: 'fp-badge--info',
  accepted: 'fp-badge--success',
  expired: 'fp-badge--danger',
  cancelled: 'fp-badge--danger',
}

export default function QuoteDetail({ quoteId, onClose, onAddVersion, includeInPipeline, onPipelineChange, isReadOnly = false, onDealStatusChange }) {
  const token = localStorage.getItem('token')
  const [quote, setQuote] = useState(null)
  const [versionsList, setVersionsList] = useState([])
  const [selectedVersion, setSelectedVersion] = useState(null)
  const [lineItems, setLineItems] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)
  const [toast, setToast] = useState(null)
  // Pipeline inclusion is owned by the parent quotes list — seed from prop and
  // re-sync whenever the parent's value changes (e.g. after refresh()).
  const [pipelineIncluded, setPipelineIncluded] = useState(!!includeInPipeline)
  useEffect(() => { setPipelineIncluded(!!includeInPipeline) }, [includeInPipeline])
  // Set when PATCH /quotes/{id}/status response signals suggest_mark_won — the
  // banner with Yes / Not yet renders until the user resolves it.
  const [showWonPrompt, setShowWonPrompt] = useState(false)

  // Documents (migration 033). The list is shown to everyone; upload is
  // channel_manager+ only; delete is channel_ops_admin / system_admin only.
  // ``currentUserRole`` is fetched once on mount via /auth/me — the API is
  // role-gated server-side anyway, this just keeps the UI from offering
  // buttons the caller can't use.
  const [documents, setDocuments] = useState([])
  const [documentsLoading, setDocumentsLoading] = useState(false)
  const [currentUserRole, setCurrentUserRole] = useState(null)
  const [showAttachForm, setShowAttachForm] = useState(false)
  // Sprint 21 hotfix FPRM-355: two-path attach flow. 'upload' lets the user
  // upload a brand-new file and attach it in one step; 'pick' lets them
  // pick an existing partner_document and attach a reference only.
  const [attachMode, setAttachMode] = useState('upload')
  const [attachType, setAttachType] = useState('quote_acceptance')
  const [attachFile, setAttachFile] = useState(null)
  const [attachNotes, setAttachNotes] = useState('')
  const [attachError, setAttachError] = useState(null)
  const [attachSaving, setAttachSaving] = useState(false)
  // Pick-existing tab state
  const [pickList, setPickList] = useState([])
  const [pickLoading, setPickLoading] = useState(false)
  const [pickSearch, setPickSearch] = useState('')
  const [pickAttachingId, setPickAttachingId] = useState(null)
  // Sprint 22 / FPRM-378 -- gate UI feedback. Rules fetched once on mount;
  // matched client-side against the document type field.
  const [documentTypeRules, setDocumentTypeRules] = useState([])
  const canUploadDocument = (
    currentUserRole === 'system_admin'
    || currentUserRole === 'channel_ops_admin'
    || currentUserRole === 'channel_manager'
  )
  const canDeleteDocument = (
    currentUserRole === 'system_admin' || currentUserRole === 'channel_ops_admin'
  )
  // AD-35 (FPRM-389): partner roles may attach a proof-of-acceptance document
  // and mark their own-org quote accepted -- even though the portal renders the
  // detail read-only for every other action. Tenant scope is enforced
  // server-side. They never see retract/delete/edit/sent/expire/add-version.
  const isPartner = currentUserRole === 'partner_admin' || currentUserRole === 'partner_user'
  const canAttachAcceptance = canUploadDocument || isPartner
  const hasAcceptanceDoc = documents.some((d) => d.document_type === 'quote_acceptance')

  useEffect(() => {
    if (!token) return
    fetch(`${API}/auth/me`, { headers: { Authorization: `Bearer ${token}` } })
      .then((r) => (r.ok ? r.json() : null))
      .then((me) => { if (me?.role) setCurrentUserRole(me.role) })
      .catch(() => {})
  }, [token])

  // Sprint 22 / FPRM-378 -- fetch document_type_rules once on mount so the
  // upload-new tab can show a gate-info hint when the user types a known
  // document type. Failure is silent: the hint just won't render.
  useEffect(() => {
    if (!token) return
    fetch(`${API}/admin/document-type-rules`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((r) => (r.ok ? r.json() : []))
      .then((rules) => Array.isArray(rules) && setDocumentTypeRules(rules))
      .catch(() => {})
  }, [token])

  const loadDocuments = useCallback(async () => {
    if (!quoteId || !token) return
    setDocumentsLoading(true)
    try {
      // Sprint 21 / AD-33 -- documents now live in partner_documents and are
      // linked to the quote via document_references. The new
      // /quotes/{id}/attached-documents endpoint joins the two.
      const r = await fetch(`${API}/quotes/${quoteId}/attached-documents`, {
        headers: { Authorization: `Bearer ${token}` },
      })
      if (!r.ok) {
        setDocuments([])
        return
      }
      const rows = await r.json()
      // Adapt to the shape the existing render logic expects:
      // {id, document_type, file_name, file_size_bytes, uploaded_at, notes}
      setDocuments(rows.map((row) => ({
        id: row.document_id,
        reference_id: row.reference_id,
        partner_org_id: row.partner_org_id,
        document_type: row.label || row.document_type,
        file_name: row.document_name,
        file_size_bytes: row.file_size_bytes,
        uploaded_at: row.uploaded_at,
        notes: null,
      })))
    } catch {
      setDocuments([])
    } finally {
      setDocumentsLoading(false)
    }
  }, [quoteId, token])

  useEffect(() => { loadDocuments() }, [loadDocuments])

  const loadQuote = useCallback(async () => {
    setError(null)
    try {
      const [qRes, vRes] = await Promise.all([
        fetch(`${API}/quotes/${quoteId}`, { headers: { Authorization: `Bearer ${token}` } }),
        fetch(`${API}/quotes/${quoteId}/versions`, { headers: { Authorization: `Bearer ${token}` } }),
      ])
      const q = await qRes.json()
      const v = await vRes.json()
      if (!qRes.ok) throw new Error(typeof q.detail === 'string' ? q.detail : `HTTP ${qRes.status}`)
      if (!vRes.ok) throw new Error(typeof v.detail === 'string' ? v.detail : `HTTP ${vRes.status}`)
      setQuote(q)
      setVersionsList(v)
      const active = q.active_version_data
      setSelectedVersion(active)
      setLineItems(active?.line_items || [])
    } catch (e) {
      setError(e.message || String(e))
    } finally {
      setLoading(false)
    }
  }, [quoteId, token])

  useEffect(() => { if (quoteId && token) loadQuote() }, [quoteId, token, loadQuote])

  function showToast(msg) {
    setToast(msg)
    setTimeout(() => setToast(null), 4000)
  }

  async function selectVersion(versionNumber) {
    if (!quote) return
    if (selectedVersion && selectedVersion.version_number === versionNumber) return
    setBusy(true)
    try {
      // re-fetch quote to get the requested version's line items (only active version comes back with items by default)
      // workaround: use the current active or, if not the requested one, hit /versions/X by fetching the full quote w/ active set
      // Simpler: keep what we have and refetch
      if (versionNumber === quote.active_version && quote.active_version_data) {
        setSelectedVersion(quote.active_version_data)
        setLineItems(quote.active_version_data.line_items || [])
      } else {
        // The current API only returns active_version_data on GET /quotes/{id}.
        // To show another version's lines, set it active temporarily — but that mutates state.
        // Instead: show summary only for non-active versions.
        const v = versionsList.find((x) => x.version_number === versionNumber)
        if (v) {
          setSelectedVersion({ ...v, line_items: null })
          setLineItems([])
        }
      }
    } finally {
      setBusy(false)
    }
  }

  async function setActive(versionNumber) {
    if (busy) return
    setBusy(true); setError(null)
    try {
      const r = await fetch(`${API}/quotes/${quoteId}/active-version`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({ version_number: versionNumber }),
      })
      const body = await r.json().catch(() => ({}))
      if (!r.ok) throw new Error(typeof body.detail === 'string' ? body.detail : `HTTP ${r.status}`)
      await loadQuote()
      showToast(`Version ${versionNumber} is now active`)
    } catch (e) {
      setError(e.message || String(e))
    } finally {
      setBusy(false)
    }
  }

  async function markAsSent() {
    if (busy || !quote) return
    setBusy(true); setError(null)
    try {
      const r = await fetch(`${API}/quotes/${quoteId}/status`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({ status: 'sent' }),
      })
      const body = await r.json().catch(() => ({}))
      if (!r.ok) throw new Error(typeof body.detail === 'string' ? body.detail : `HTTP ${r.status}`)
      await loadQuote()
      showToast('Quote marked as Sent')
    } catch (e) {
      setError(e.message || String(e))
    } finally {
      setBusy(false)
    }
  }

  async function setStatus(newStatus, toastMsg) {
    if (busy || !quote) return
    setBusy(true); setError(null)
    try {
      const r = await fetch(`${API}/quotes/${quoteId}/status`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({ status: newStatus }),
      })
      const body = await r.json().catch(() => ({}))
      if (!r.ok) throw new Error(typeof body.detail === 'string' ? body.detail : `HTTP ${r.status}`)
      await loadQuote()
      showToast(toastMsg)
      // Backend advises whether to prompt for Mark-as-Won (deal still
      // approved AND no other draft/sent quotes pending). Never auto-close.
      if (body && body.suggest_mark_won === true) {
        setShowWonPrompt(true)
      }
    } catch (e) {
      setError(e.message || String(e))
    } finally {
      setBusy(false)
    }
  }

  async function handleRetractAcceptance() {
    if (busy || !quote) return
    if (!window.confirm(
      'Retract this accepted quote back to Sent? This should only be done '
      + 'to correct an error. This action is logged.'
    )) return
    setBusy(true); setError(null)
    try {
      const r = await fetch(`${API}/quotes/${quoteId}/status`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({ status: 'sent' }),
      })
      const body = await r.json().catch(() => ({}))
      if (!r.ok) throw new Error(typeof body.detail === 'string' ? body.detail : `HTTP ${r.status}`)
      await loadQuote()
      showToast('Acceptance retracted — quote returned to Sent')
    } catch (e) {
      setError(e.message || String(e))
    } finally {
      setBusy(false)
    }
  }

  async function handleMarkWonFromPrompt() {
    if (busy || !quote) return
    setBusy(true); setError(null)
    try {
      const r = await fetch(`${API}/internal/deals/${quote.deal_id}/won`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
      })
      const body = await r.json().catch(() => ({}))
      if (!r.ok) throw new Error(typeof body.detail === 'string' ? body.detail : `HTTP ${r.status}`)
      showToast('Deal marked as Won — quotes updated')
      setShowWonPrompt(false)
      if (typeof onDealStatusChange === 'function') onDealStatusChange()
      if (typeof onClose === 'function') onClose()
    } catch (e) {
      setError(e.message || String(e))
    } finally {
      setBusy(false)
    }
  }

  async function togglePipelineInclusion() {
    if (busy || !quote) return
    const next = !pipelineIncluded
    setBusy(true); setError(null)
    setPipelineIncluded(next)
    try {
      const r = await fetch(`${API}/quotes/${quoteId}/pipeline-inclusion`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({ include_in_pipeline: next }),
      })
      const body = await r.json().catch(() => ({}))
      if (!r.ok) throw new Error(typeof body.detail === 'string' ? body.detail : `HTTP ${r.status}`)
      showToast(next ? 'Quote included in pipeline' : 'Quote removed from pipeline')
      if (typeof onPipelineChange === 'function') onPipelineChange(next)
    } catch (e) {
      setPipelineIncluded(!next)
      setError(e.message || String(e))
    } finally {
      setBusy(false)
    }
  }

  const [pdfGenerating, setPdfGenerating] = useState(false)
  const [pdfAvailable, setPdfAvailable] = useState(false)
  const [scenarios, setScenarios] = useState([])
  const [activeScenario, setActiveScenario] = useState(null)
  const [scenarioBusy, setScenarioBusy] = useState(false)

  useEffect(() => {
    setPdfAvailable(!!selectedVersion?.pdf_generated_at)
  }, [selectedVersion])

  useEffect(() => {
    if (!quoteId || !token) return
    fetch(`${API}/quotes/${quoteId}/scenarios`, { headers: { Authorization: `Bearer ${token}` } })
      .then(async (r) => {
        if (!r.ok) return { scenarios: [], active_scenario: null }
        return r.json()
      })
      .then((data) => {
        setScenarios(data.scenarios || [])
        setActiveScenario(data.active_scenario || null)
      })
      .catch(() => {})
  }, [quoteId, token, quote])

  async function handleSelectScenario(scenario) {
    if (scenarioBusy) return
    setScenarioBusy(true); setError(null)
    try {
      const r1 = await fetch(`${API}/quotes/${quoteId}/active-scenario`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({ scenario_label: scenario.scenario_label }),
      })
      if (!r1.ok) {
        const body = await r1.json().catch(() => ({}))
        throw new Error(typeof body.detail === 'string' ? body.detail : `HTTP ${r1.status}`)
      }
      const r2 = await fetch(`${API}/quotes/${quoteId}/active-version`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({ version_number: scenario.version_number, scenario_label: scenario.scenario_label }),
      })
      if (!r2.ok) {
        const body = await r2.json().catch(() => ({}))
        throw new Error(typeof body.detail === 'string' ? body.detail : `HTTP ${r2.status}`)
      }
      await loadQuote()
      showToast(`Selected ${scenario.scenario_label} scenario`)
    } catch (e) {
      setError(e.message || String(e))
    } finally {
      setScenarioBusy(false)
    }
  }

  async function handleGeneratePdf() {
    if (pdfGenerating || !selectedVersion) return
    setPdfGenerating(true); setError(null)
    try {
      const r = await fetch(`${API}/quotes/${quoteId}/versions/${selectedVersion.version_number}/generate-pdf`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
      })
      const body = await r.json().catch(() => ({}))
      if (!r.ok) throw new Error(typeof body.detail === 'string' ? body.detail : `HTTP ${r.status}`)
      setPdfAvailable(true)
      showToast('PDF generated')
      await loadQuote()
    } catch (e) {
      setError(e.message || String(e))
    } finally {
      setPdfGenerating(false)
    }
  }

  const _MAX_DOC_BYTES = 25 * 1024 * 1024  // AD-37: aligned with the 25 MB partner-documents cap

  async function handleAttachDocument() {
    // Sprint 21 / AD-33 -- two-step flow: upload bytes into the centralised
    // partner_documents store, then create a document_references row linking
    // the new document to this quote (entity_type='quote', label=attachType).
    setAttachError(null)
    if (!attachFile) {
      setAttachError('Choose a file to attach')
      return
    }
    if (attachFile.size > _MAX_DOC_BYTES) {
      setAttachError('File too large. Maximum upload size is 25 MB.')
      return
    }
    if (!quote?.partner_org_id) {
      setAttachError('Cannot attach: partner org missing from quote')
      return
    }
    setAttachSaving(true)
    try {
      const dataUrl = await new Promise((resolve, reject) => {
        const reader = new FileReader()
        reader.onload = () => resolve(reader.result)
        reader.onerror = () => reject(new Error('Could not read file'))
        reader.readAsDataURL(attachFile)
      })
      const b64 = String(dataUrl).split(',', 2)[1] || ''
      const uploadRes = await fetch(`${API}/partners/${quote.partner_org_id}/documents`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({
          document_type: attachType,
          document_name: attachFile.name,
          file_data: b64,
          file_size_bytes: attachFile.size,
          mime_type: attachFile.type || 'application/octet-stream',
        }),
      })
      const uploadBody = await uploadRes.json().catch(() => ({}))
      if (!uploadRes.ok) {
        throw new Error(typeof uploadBody.detail === 'string' ? uploadBody.detail : `HTTP ${uploadRes.status}`)
      }
      const refRes = await fetch(
        `${API}/partners/${quote.partner_org_id}/documents/${uploadBody.id}/references`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
          body: JSON.stringify({
            entity_type: 'quote',
            entity_id: quoteId,
            label: attachType,
          }),
        },
      )
      if (!refRes.ok) {
        const body = await refRes.json().catch(() => ({}))
        throw new Error(typeof body.detail === 'string' ? body.detail : `HTTP ${refRes.status}`)
      }
      await loadDocuments()
      setShowAttachForm(false)
      setAttachFile(null)
      setAttachNotes('')
      setAttachType('quote_acceptance')
      showToast('Document attached')
    } catch (e) {
      setAttachError(e.message || String(e))
    } finally {
      setAttachSaving(false)
    }
  }

  async function handleDownloadDocument(doc) {
    try {
      const partnerOrgId = doc.partner_org_id || quote?.partner_org_id
      const r = await fetch(`${API}/partners/${partnerOrgId}/documents/${doc.id}/download`, {
        headers: { Authorization: `Bearer ${token}` },
      })
      if (!r.ok) {
        const body = await r.json().catch(() => ({}))
        throw new Error(typeof body.detail === 'string' ? body.detail : `HTTP ${r.status}`)
      }
      const blob = await r.blob()
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = doc.file_name
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      URL.revokeObjectURL(url)
    } catch (e) {
      setError(e.message || String(e))
    }
  }

  async function handleDeleteDocument(doc) {
    // Sprint 21 / AD-33 -- detach by removing the document_references row,
    // leaving the underlying partner_documents row intact so other links
    // (and the file content) survive. A full hard-delete of the document
    // happens from the Documents page.
    if (!window.confirm(`Remove ${doc.file_name} from this quote?`)) return
    try {
      const partnerOrgId = doc.partner_org_id || quote?.partner_org_id
      const r = await fetch(
        `${API}/partners/${partnerOrgId}/documents/${doc.id}/references/${doc.reference_id}`,
        {
          method: 'DELETE',
          headers: { Authorization: `Bearer ${token}` },
        },
      )
      if (!r.ok) {
        const body = await r.json().catch(() => ({}))
        throw new Error(typeof body.detail === 'string' ? body.detail : `HTTP ${r.status}`)
      }
      await loadDocuments()
      showToast('Document removed from quote')
    } catch (e) {
      setError(e.message || String(e))
    }
  }

  function formatFileSize(bytes) {
    if (bytes == null) return '—'
    if (bytes < 1024) return `${bytes} B`
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
  }

  // Sprint 21 hotfix FPRM-355: list existing partner documents available
  // to attach. We fetch the full list so the user can pick any document on
  // file (not just approved ones); the gate on quote.status='accepted' no
  // longer requires approved status per FPRM-353.
  const loadPickList = useCallback(async () => {
    if (!quote?.partner_org_id || !token) return
    setPickLoading(true)
    try {
      const r = await fetch(
        `${API}/partners/${quote.partner_org_id}/documents`,
        { headers: { Authorization: `Bearer ${token}` } },
      )
      if (!r.ok) {
        setPickList([])
        return
      }
      const body = await r.json()
      const items = Array.isArray(body) ? body : body.items || []
      // Hide docs already attached to this quote.
      const attached = new Set(documents.map((d) => d.id))
      setPickList(items.filter((d) => !attached.has(d.id)))
    } catch {
      setPickList([])
    } finally {
      setPickLoading(false)
    }
  }, [quote, token, documents])

  // Refresh the pick list whenever the user opens the pick tab or the set
  // of already-attached documents changes.
  useEffect(() => {
    if (showAttachForm && attachMode === 'pick') {
      loadPickList()
    }
  }, [showAttachForm, attachMode, loadPickList])

  async function handleAttachExistingDocument(doc) {
    if (!quote?.partner_org_id) return
    setAttachError(null)
    setPickAttachingId(doc.id)
    try {
      const r = await fetch(
        `${API}/partners/${quote.partner_org_id}/documents/${doc.id}/references`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
          body: JSON.stringify({
            entity_type: 'quote',
            entity_id: quoteId,
            label: doc.document_type || 'quote_acceptance',
          }),
        },
      )
      const body = await r.json().catch(() => ({}))
      if (!r.ok) {
        throw new Error(typeof body.detail === 'string' ? body.detail : `HTTP ${r.status}`)
      }
      await loadDocuments()
      setShowAttachForm(false)
      setAttachMode('upload')
      showToast('Document attached')
    } catch (e) {
      setAttachError(e.message || String(e))
    } finally {
      setPickAttachingId(null)
    }
  }

  const _DOC_TYPE_LABEL = {
    quote_acceptance: 'Quote Acceptance',
    purchase_order: 'Purchase Order',
    signed_proposal: 'Signed Proposal',
    other: 'Other',
  }

  async function handleDownloadPdf() {
    if (!selectedVersion) return
    try {
      const r = await fetch(`${API}/quotes/${quoteId}/versions/${selectedVersion.version_number}/pdf`, {
        headers: { Authorization: `Bearer ${token}` },
      })
      if (!r.ok) {
        const body = await r.json().catch(() => ({}))
        throw new Error(typeof body.detail === 'string' ? body.detail : `HTTP ${r.status}`)
      }
      const blob = await r.blob()
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `quote-v${selectedVersion.version_number}.pdf`
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      URL.revokeObjectURL(url)
    } catch (e) {
      setError(e.message || String(e))
    }
  }

  if (loading) return <div className="fp-card" style={{ color: '#64748B' }}>Loading quote…</div>
  if (error && !quote) return <div className="fp-alert fp-alert--danger">{error}</div>
  if (!quote) return null

  const currency = quote.currency_code || 'USD'
  const activeVersionNum = quote.active_version
  const isTerminal = quote.status === 'accepted' || quote.status === 'expired' || quote.status === 'cancelled'

  return (
    <div>
      <div className="fp-page-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: 12 }}>
        <div>
          <h2 className="fp-page-title">{quote.quote_name || 'Untitled Quote'}</h2>
          <div style={{ display: 'flex', gap: 12, alignItems: 'center', marginTop: 6, flexWrap: 'wrap' }}>
            <span className={`fp-badge ${STATUS_TONE[quote.status] || 'fp-badge--neutral'}`}>
              {quote.status.charAt(0).toUpperCase() + quote.status.slice(1)}
            </span>
            <span style={{ fontSize: 13, color: '#64748B' }}>Currency: <strong>{currency}</strong></span>
            <span style={{ fontSize: 13, color: '#64748B' }}>Active: v{activeVersionNum}</span>
          </div>
        </div>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          {!isReadOnly && quote.status === 'draft' && (
            <button type="button" disabled={busy} onClick={markAsSent} className="fp-btn fp-btn--secondary">
              Mark as Sent
            </button>
          )}
          {(!isReadOnly || isPartner) && quote.status === 'sent' && (
            <button type="button"
              disabled={busy || !hasAcceptanceDoc}
              title={!hasAcceptanceDoc ? 'Attach proof of acceptance before marking as accepted' : undefined}
              onClick={() => setStatus('accepted', 'Quote marked as Accepted')}
              className="fp-btn fp-btn--success">
              Mark as Accepted
            </button>
          )}
          {!isReadOnly && quote.status === 'sent' && (
            <button type="button" disabled={busy}
              onClick={() => setStatus('expired', 'Quote marked as Expired')}
              className="fp-btn fp-btn--ghost">
              Mark as Expired
            </button>
          )}
          {!isReadOnly && (quote.status === 'draft' || quote.status === 'sent') && (
            <button type="button" disabled={busy}
              onClick={() => {
                if (window.confirm('Cancel this quote? This cannot be undone.')) {
                  setStatus('cancelled', 'Quote cancelled')
                }
              }}
              className="fp-btn fp-btn--danger">
              Cancel Quote
            </button>
          )}
          {!isReadOnly && onAddVersion && !isTerminal && (
            <button type="button" disabled={busy} onClick={() => onAddVersion(quote)} className="fp-btn fp-btn--primary">
              Add Version
            </button>
          )}
          {!isReadOnly && quote.status === 'accepted' && currentUserRole === 'system_admin' && (
            <button type="button" disabled={busy}
              onClick={handleRetractAcceptance}
              className="fp-btn fp-btn--ghost"
              title="Roll the quote back to Sent for correction. Audit-logged.">
              Retract Acceptance
            </button>
          )}
          {onClose && (
            <button type="button" onClick={onClose} className="fp-btn fp-btn--ghost">Close</button>
          )}
        </div>
      </div>

      {error && <div className="fp-alert fp-alert--danger" style={{ marginBottom: 12 }}>{error}</div>}

      {showWonPrompt && !isReadOnly && (
        <div className="fp-alert fp-alert--success" role="status" style={{ marginBottom: 12, display: 'flex', flexWrap: 'wrap', gap: 12, alignItems: 'center', justifyContent: 'space-between' }}>
          <span><strong>Quote accepted.</strong> Would you like to mark this deal as Won?</span>
          <span style={{ display: 'flex', gap: 8 }}>
            <button type="button" className="fp-btn fp-btn--success" disabled={busy} onClick={handleMarkWonFromPrompt}>
              Yes, Mark as Won
            </button>
            <button type="button" className="fp-btn fp-btn--ghost" disabled={busy} onClick={() => setShowWonPrompt(false)}>
              Not yet
            </button>
          </span>
        </div>
      )}

      <section className="fp-card" style={{ marginBottom: 16 }}>
        <h3 className="fp-section-title">{isReadOnly ? 'Composition' : 'Pipeline & composition'}</h3>
        <div style={{ display: 'flex', gap: 24, flexWrap: 'wrap', alignItems: 'flex-start' }}>
          {!isReadOnly && (
            <div style={{ flex: '1 1 240px' }}>
              <div style={{ fontSize: 13, color: '#64748B', marginBottom: 6 }}>Pipeline inclusion</div>
              <label style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: busy ? 'wait' : 'pointer' }}>
                <input
                  type="checkbox"
                  checked={pipelineIncluded}
                  disabled={busy}
                  onChange={togglePipelineInclusion}
                />
                <span style={{ fontWeight: 600, color: pipelineIncluded ? '#15803D' : '#64748B' }}>
                  {pipelineIncluded ? '✅ Included in pipeline' : '— Not included in pipeline'}
                </span>
              </label>
              <div style={{ fontSize: 12, color: '#94A3B8', marginTop: 6 }}>
                Channel managers control whether this quote contributes to the cross-deal pipeline total.
              </div>
            </div>
          )}
          <div style={{ flex: '1 1 240px' }}>
            <div style={{ fontSize: 13, color: '#64748B', marginBottom: 6 }}>Quote composition</div>
            <div style={{ fontWeight: 600, color: '#1E293B' }}>
              {(() => {
                const sw = !!selectedVersion?.includes_software
                const sv = !!selectedVersion?.includes_services
                if (sw && sv) return 'Software + Services'
                if (sw) return 'Software only'
                if (sv) return 'Services only'
                return '—'
              })()}
            </div>
            <div style={{ fontSize: 12, color: '#94A3B8', marginTop: 6 }}>
              Services quoting is read-only until the services pricing module ships.
            </div>
          </div>
        </div>
      </section>

      <section className="fp-card" style={{ marginBottom: 16 }}>
        <h3 className="fp-section-title">Versions</h3>
        {isTerminal ? (
          // Terminal quotes (accepted / expired / cancelled) freeze on whichever
          // version was active at the time of the transition. Other versions
          // become irrelevant -- showing them as switchable tabs implies
          // history is browsable when in fact the locked version is the only
          // meaningful one. Render a single read-only label instead.
          <div style={{ fontSize: 13, color: '#64748B' }}>
            Locked at active version:{' '}
            <strong style={{ color: '#1E293B' }}>
              v{activeVersionNum}{quote.active_scenario ? ` (${quote.active_scenario})` : ''}
            </strong>
          </div>
        ) : (
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            {versionsList.map((v) => {
              const isSelected = selectedVersion && selectedVersion.version_number === v.version_number
              const isActive = v.version_number === activeVersionNum
              return (
                <button key={v.version_number} type="button" onClick={() => selectVersion(v.version_number)}
                  style={{
                    padding: '6px 12px',
                    borderRadius: 6,
                    border: isSelected ? '2px solid #1A6EBB' : '1px solid #E0E4EA',
                    background: isActive ? '#1A6EBB' : '#fff',
                    color: isActive ? '#fff' : '#1E293B',
                    fontWeight: isActive ? 700 : 500,
                    cursor: 'pointer',
                    opacity: v.is_deleted ? 0.4 : 1,
                  }}>
                  v{v.version_number}{v.scenario_label ? ` (${v.scenario_label})` : ''}{isActive ? ' ★' : ''}
                </button>
              )
            })}
          </div>
        )}
        {!isReadOnly && selectedVersion && selectedVersion.version_number !== activeVersionNum && !selectedVersion.is_deleted && !isTerminal && (
          <button type="button" disabled={busy} onClick={() => setActive(selectedVersion.version_number)}
            className="fp-btn fp-btn--ghost" style={{ marginTop: 12 }}>
            Set as Active
          </button>
        )}
      </section>

      {scenarios.length > 0 && (
        <section className="fp-card" style={{ marginBottom: 16 }}>
          <h3 className="fp-section-title">Scenario Comparison</h3>
          <div style={{ display: 'grid', gridTemplateColumns: `repeat(${scenarios.length}, minmax(0, 1fr))`, gap: 12 }}>
            {scenarios.map((scenario) => {
              const isActive = scenario.scenario_label === activeScenario
              return (
                <div key={scenario.scenario_label}
                  style={{
                    border: isActive ? '2px solid #1A6EBB' : '1px solid #E0E4EA',
                    borderRadius: 8,
                    overflow: 'hidden',
                    background: '#fff',
                  }}>
                  <div style={{
                    background: '#1A6EBB', color: '#fff',
                    padding: '8px 12px', fontWeight: 700,
                    display: 'flex', justifyContent: 'space-between',
                  }}>
                    <span>{isActive ? '⭐ ' : ''}{scenario.scenario_label.charAt(0).toUpperCase() + scenario.scenario_label.slice(1)}</span>
                    <span style={{ fontSize: 12, opacity: 0.85 }}>v{scenario.version_number}</span>
                  </div>
                  <div style={{ padding: 14 }}>
                    <div style={{ fontSize: 13, color: '#64748B', textTransform: 'capitalize', marginBottom: 8 }}>
                      {scenario.feature_plan} Plan
                    </div>
                    <div style={{ fontSize: 22, fontWeight: 700, color: '#1A6EBB', marginBottom: 4 }}>
                      {fmtMoney(scenario.grand_total_after_discount, currency)}
                    </div>
                    <div style={{ fontSize: 11, color: '#94A3B8', marginBottom: 14 }}>per year</div>
                    {isActive ? (
                      <div style={{ color: '#1A6EBB', fontWeight: 600, fontSize: 13 }}>✓ Selected</div>
                    ) : !isReadOnly ? (
                      <button
                        type="button"
                        disabled={scenarioBusy}
                        onClick={() => handleSelectScenario(scenario)}
                        className="fp-btn fp-btn--primary"
                        style={{ width: '100%' }}
                      >
                        Select This Option
                      </button>
                    ) : null}
                  </div>
                </div>
              )
            })}
          </div>
        </section>
      )}

      <section className="fp-card" style={{ marginBottom: 16 }}>
        <h3 className="fp-section-title">Line items{selectedVersion ? ` — Version ${selectedVersion.version_number}` : ''}</h3>
        {!lineItems || lineItems.length === 0 ? (
          <div style={{ color: '#64748B', fontSize: 13 }}>
            {selectedVersion && selectedVersion.version_number !== activeVersionNum
              ? 'Line items only display for the active version. Switch to active or use Set as Active to view.'
              : 'No line items.'}
          </div>
        ) : (
          <table style={{ width: '100%', fontSize: 13, borderCollapse: 'collapse' }}>
            <thead>
              <tr style={{ background: '#1A6EBB', color: '#fff' }}>
                <th style={{ textAlign: 'left', padding: 8 }}>Description</th>
                <th style={{ textAlign: 'right', padding: 8 }}>Qty</th>
                <th style={{ textAlign: 'right', padding: 8 }}>Unit Price</th>
                <th style={{ textAlign: 'right', padding: 8 }}>Discount %</th>
                <th style={{ textAlign: 'right', padding: 8 }}>Total Before</th>
                <th style={{ textAlign: 'right', padding: 8 }}>Total After</th>
              </tr>
            </thead>
            <tbody>
              {lineItems.map((li) => (
                <tr key={li.id || `${li.line_order}-${li.line_type}`} style={{
                  borderBottom: '1px solid #F1F5F9',
                  background: li.line_type === 'free_allocation' ? '#F0FDF4' : 'transparent',
                  color: li.line_type === 'free_allocation' ? '#15803D' : 'inherit',
                  fontStyle: li.line_type === 'free_allocation' ? 'italic' : 'normal',
                }}>
                  <td style={{ padding: 8 }}>{li.description}</td>
                  <td style={{ padding: 8, textAlign: 'right' }}>{li.quantity}</td>
                  <td style={{ padding: 8, textAlign: 'right' }}>{Number(li.unit_price) > 0 ? fmtMoney(li.unit_price, currency) : '—'}</td>
                  <td style={{ padding: 8, textAlign: 'right' }}>{Number(li.discount_pct) > 0 ? `${Number(li.discount_pct).toFixed(0)}%` : '—'}</td>
                  <td style={{ padding: 8, textAlign: 'right' }}>{fmtMoney(li.total_before_discount, currency)}</td>
                  <td style={{ padding: 8, textAlign: 'right' }}>{fmtMoney(li.total_after_discount, currency)}</td>
                </tr>
              ))}
              <tr style={{ borderTop: '2px solid #1A6EBB', background: '#F5F7FA', fontWeight: 700 }}>
                <td style={{ padding: 8 }} colSpan={4}>Grand Total</td>
                <td style={{ padding: 8, textAlign: 'right' }}>{fmtMoney(selectedVersion?.grand_total_before_discount, currency)}</td>
                <td style={{ padding: 8, textAlign: 'right' }}>{fmtMoney(selectedVersion?.grand_total_after_discount, currency)}</td>
              </tr>
            </tbody>
          </table>
        )}
      </section>

      <section className="fp-card" style={{ marginBottom: 16 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
          <h3 className="fp-section-title" style={{ margin: 0 }}>Documents</h3>
          {(!isReadOnly || isPartner) && canAttachAcceptance && !showAttachForm && (
            <button type="button" className="fp-btn fp-btn--primary" onClick={() => setShowAttachForm(true)}>
              + Attach Document
            </button>
          )}
        </div>

        {(!isReadOnly || isPartner) && !hasAcceptanceDoc && (quote.status === 'draft' || quote.status === 'sent') && (
          <div className="fp-alert fp-alert--warning" role="status" style={{ marginBottom: 12 }}>
            ⚠️ Attach proof of acceptance before marking as accepted
          </div>
        )}

        {(!isReadOnly || isPartner) && showAttachForm && (
          <div style={{ background: '#F8FAFC', border: '1px solid #E0E4EA', borderRadius: 6, padding: 12, marginBottom: 12 }}>
            {/* Sprint 21 hotfix FPRM-355: two-path attach — Upload New or Pick Existing. */}
            <div role="tablist" style={{ display: 'flex', gap: 4, marginBottom: 12, borderBottom: '1px solid #E0E4EA' }}>
              <button
                type="button"
                role="tab"
                aria-selected={attachMode === 'upload'}
                onClick={() => { setAttachMode('upload'); setAttachError(null) }}
                disabled={attachSaving || pickAttachingId !== null}
                style={{
                  padding: '8px 14px',
                  border: 'none',
                  background: 'transparent',
                  cursor: 'pointer',
                  fontSize: 13,
                  fontWeight: attachMode === 'upload' ? 700 : 500,
                  color: attachMode === 'upload' ? '#1A6EBB' : '#64748B',
                  borderBottom: attachMode === 'upload' ? '2px solid #1A6EBB' : '2px solid transparent',
                  marginBottom: -1,
                }}
              >
                Upload New
              </button>
              <button
                type="button"
                role="tab"
                aria-selected={attachMode === 'pick'}
                onClick={() => { setAttachMode('pick'); setAttachError(null) }}
                disabled={attachSaving || pickAttachingId !== null}
                style={{
                  padding: '8px 14px',
                  border: 'none',
                  background: 'transparent',
                  cursor: 'pointer',
                  fontSize: 13,
                  fontWeight: attachMode === 'pick' ? 700 : 500,
                  color: attachMode === 'pick' ? '#1A6EBB' : '#64748B',
                  borderBottom: attachMode === 'pick' ? '2px solid #1A6EBB' : '2px solid transparent',
                  marginBottom: -1,
                }}
              >
                Pick Existing
              </button>
            </div>

            {attachMode === 'upload' && (
              <div style={{ display: 'grid', gap: 8 }}>
                <label style={{ display: 'block', fontSize: 13 }}>
                  <span style={{ display: 'block', color: '#64748B', marginBottom: 4 }}>Document type</span>
                  {/* FPRM-418 / AD-40: shared vocabulary -- identical list to the
                      Documents page; replaces the divergent 4-item list. */}
                  <DocumentTypeSelect
                    token={token}
                    value={attachType}
                    onChange={setAttachType}
                    disabled={attachSaving}
                    style={{ padding: '6px 10px', borderRadius: 6, border: '1px solid #E0E4EA', minWidth: 220 }}
                  />
                </label>
                {/* Sprint 22 / FPRM-378 -- acceptance gate UI feedback. */}
                {(() => {
                  const rule = documentTypeRules.find(
                    (r) => r.document_type.toLowerCase() === attachType.toLowerCase()
                  )
                  if (rule && rule.auto_approve) {
                    return (
                      <div style={{ fontSize: 12, color: '#2E7D32', background: '#E6F4EA', padding: '6px 10px', borderRadius: 6 }}>
                        ✓ This document type will be auto-approved on upload.
                      </div>
                    )
                  }
                  if (rule && rule.requires_approval) {
                    return (
                      <div style={{ fontSize: 12, color: '#B7791F', background: '#FEFCE8', padding: '6px 10px', borderRadius: 6 }}>
                        ⚠ This document type requires approval before it can be used to accept a quote.
                      </div>
                    )
                  }
                  if (!rule && attachType.length > 2) {
                    return (
                      <div style={{ fontSize: 12, color: '#64748B', background: '#F5F7FA', padding: '6px 10px', borderRadius: 6 }}>
                        No approval rule configured for this document type — will default to pending review.
                      </div>
                    )
                  }
                  return null
                })()}
                <label style={{ display: 'block', fontSize: 13 }}>
                  <span style={{ display: 'block', color: '#64748B', marginBottom: 4 }}>File (max 25 MB)</span>
                  <input
                    type="file"
                    onChange={(e) => setAttachFile(e.target.files?.[0] || null)}
                    disabled={attachSaving}
                  />
                </label>
                <label style={{ display: 'block', fontSize: 13 }}>
                  <span style={{ display: 'block', color: '#64748B', marginBottom: 4 }}>Notes (optional)</span>
                  <textarea
                    value={attachNotes}
                    onChange={(e) => setAttachNotes(e.target.value)}
                    rows={2}
                    style={{ width: '100%', padding: '6px 10px', borderRadius: 6, border: '1px solid #E0E4EA' }}
                    disabled={attachSaving}
                  />
                </label>
                {attachError && <div className="fp-alert fp-alert--danger" style={{ marginTop: 0 }}>{attachError}</div>}
                <div style={{ display: 'flex', gap: 8 }}>
                  <button type="button" className="fp-btn fp-btn--primary" onClick={handleAttachDocument} disabled={attachSaving}>
                    {attachSaving ? 'Uploading…' : 'Upload'}
                  </button>
                  <button type="button" className="fp-btn fp-btn--ghost"
                    onClick={() => { setShowAttachForm(false); setAttachFile(null); setAttachNotes(''); setAttachError(null); setAttachMode('upload') }}
                    disabled={attachSaving}>
                    Cancel
                  </button>
                </div>
              </div>
            )}

            {attachMode === 'pick' && (
              <div style={{ display: 'grid', gap: 8 }}>
                <input
                  type="search"
                  placeholder="Search by document name or type…"
                  value={pickSearch}
                  onChange={(e) => setPickSearch(e.target.value)}
                  disabled={pickAttachingId !== null}
                  style={{ padding: '6px 10px', borderRadius: 6, border: '1px solid #E0E4EA', fontSize: 13 }}
                />
                {attachError && <div className="fp-alert fp-alert--danger" style={{ marginTop: 0 }}>{attachError}</div>}
                {pickLoading ? (
                  <div style={{ color: '#64748B', fontSize: 13, padding: 8 }}>Loading existing documents…</div>
                ) : (() => {
                  const q = pickSearch.trim().toLowerCase()
                  const filtered = pickList.filter((d) => !q || (
                    (d.document_name || '').toLowerCase().includes(q) ||
                    (d.document_type || '').toLowerCase().includes(q)
                  ))
                  if (filtered.length === 0) {
                    return (
                      <div style={{ color: '#94A3B8', fontSize: 13, padding: 8, textAlign: 'center' }}>
                        {pickList.length === 0
                          ? 'No existing partner documents available to attach.'
                          : 'No documents match the search.'}
                      </div>
                    )
                  }
                  return (
                    <table style={{ width: '100%', fontSize: 13, borderCollapse: 'collapse' }}>
                      <thead>
                        <tr style={{ background: '#F1F5F9', textAlign: 'left' }}>
                          <th style={{ padding: 6 }}>Name</th>
                          <th style={{ padding: 6 }}>Type</th>
                          <th style={{ padding: 6 }}>Status</th>
                          <th style={{ padding: 6 }}>Uploaded</th>
                          <th style={{ padding: 6, textAlign: 'right' }}>Action</th>
                        </tr>
                      </thead>
                      <tbody>
                        {filtered.map((d) => (
                          <tr key={d.id} style={{ borderBottom: '1px solid #E2E8F0' }}>
                            <td style={{ padding: 6 }}>
                              {d.document_name}
                              {/* Sprint 22 -- version badge so the user knows
                                  which version is being attached. */}
                              <span style={{
                                marginLeft: 6, fontSize: 11, color: '#1A6EBB',
                                fontWeight: 600,
                              }}>
                                v{d.current_version_number ?? 1}
                                {d.version_count > 1 && (
                                  <span style={{ color: '#94A3B8', fontWeight: 400 }}>
                                    {' '}(of {d.version_count})
                                  </span>
                                )}
                              </span>
                            </td>
                            <td style={{ padding: 6, color: '#64748B' }}>{d.document_type}</td>
                            <td style={{ padding: 6, color: '#64748B' }}>{d.status}</td>
                            <td style={{ padding: 6, color: '#64748B' }}>
                              {d.uploaded_at ? new Date(d.uploaded_at).toLocaleDateString() : '—'}
                            </td>
                            <td style={{ padding: 6, textAlign: 'right' }}>
                              <button
                                type="button"
                                className="fp-btn fp-btn--primary"
                                disabled={pickAttachingId !== null}
                                onClick={() => handleAttachExistingDocument(d)}
                              >
                                {pickAttachingId === d.id ? 'Attaching…' : 'Attach'}
                              </button>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  )
                })()}
                <div style={{ display: 'flex', gap: 8 }}>
                  <button type="button" className="fp-btn fp-btn--ghost"
                    onClick={() => { setShowAttachForm(false); setAttachError(null); setAttachMode('upload'); setPickSearch('') }}
                    disabled={pickAttachingId !== null}>
                    Cancel
                  </button>
                </div>
              </div>
            )}
          </div>
        )}

        {documentsLoading ? (
          <div style={{ color: '#64748B', fontSize: 13 }}>Loading documents…</div>
        ) : documents.length === 0 ? (
          <div style={{ color: '#94A3B8', fontSize: 13 }}>No documents attached yet.</div>
        ) : (
          <table style={{ width: '100%', fontSize: 13, borderCollapse: 'collapse' }}>
            <thead>
              <tr style={{ background: '#F5F7FA', textAlign: 'left' }}>
                <th style={{ padding: 8 }}>Type</th>
                <th style={{ padding: 8 }}>File</th>
                <th style={{ padding: 8 }}>Size</th>
                <th style={{ padding: 8 }}>Uploaded</th>
                <th style={{ padding: 8 }}>Notes</th>
                <th style={{ padding: 8, textAlign: 'right' }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {documents.map((doc) => (
                <tr key={doc.id} style={{ borderBottom: '1px solid #F1F5F9' }}>
                  <td style={{ padding: 8 }}>
                    <span className="fp-badge fp-badge--neutral">
                      {_DOC_TYPE_LABEL[doc.document_type] || doc.document_type}
                    </span>
                  </td>
                  <td style={{ padding: 8 }}>{doc.file_name}</td>
                  <td style={{ padding: 8, color: '#64748B' }}>{formatFileSize(doc.file_size_bytes)}</td>
                  <td style={{ padding: 8, color: '#64748B' }}>
                    {doc.uploaded_at ? new Date(doc.uploaded_at).toLocaleDateString() : '—'}
                  </td>
                  <td style={{ padding: 8, color: '#64748B' }}>{doc.notes || '—'}</td>
                  <td style={{ padding: 8, textAlign: 'right' }}>
                    <button type="button" onClick={() => handleDownloadDocument(doc)}
                      className="fp-btn fp-btn--ghost" style={{ marginRight: 6 }}>
                      Download
                    </button>
                    {!isReadOnly && canDeleteDocument && (
                      <button type="button" onClick={() => handleDeleteDocument(doc)} className="fp-btn fp-btn--danger">
                        Delete
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      <section className="fp-card" style={{ marginBottom: 16 }}>
        <h3 className="fp-section-title">PDF</h3>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          {!isReadOnly && (
            <button type="button" data-action="generate-pdf" disabled={pdfGenerating || !selectedVersion}
              onClick={handleGeneratePdf} className="fp-btn fp-btn--secondary">
              {pdfGenerating ? 'Generating…' : 'Generate PDF'}
            </button>
          )}
          <button type="button" data-action="download-pdf" disabled={!pdfAvailable}
            onClick={handleDownloadPdf} className="fp-btn fp-btn--primary">
            Download PDF
          </button>
        </div>
        {selectedVersion?.pdf_generated_at && (
          <div style={{ marginTop: 8, fontSize: 12, color: '#64748B' }}>
            Last generated: {new Date(selectedVersion.pdf_generated_at).toLocaleString()}
          </div>
        )}
      </section>

      {toast && (
        <div role="status" style={{ position: 'fixed', bottom: 24, right: 24, background: '#1b8743', color: '#fff', padding: '12px 18px', borderRadius: 8, boxShadow: '0 6px 24px rgba(0,0,0,0.15)', fontSize: 14, zIndex: 1100 }}>
          {toast}
        </div>
      )}
    </div>
  )
}
