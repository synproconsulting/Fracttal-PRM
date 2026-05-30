// Session teardown helpers (Sprint 24 / FPRM-420).
//
// A document/asset preview is opened by fetching the bytes with the bearer
// token and handing the response to URL.createObjectURL, then opening that
// blob: URL in a new tab. Those object-URLs stay valid until explicitly
// revoked. Before this change the partner Documents preview revoked its URL on
// a 30s timer, so after logout -> login as a *different* org the previous org's
// preview blob remained openable until a hard refresh wiped the page's blob
// store. That is a cross-tenant data leak in the client cache (the backend
// already 403s a cross-org re-fetch).
//
// Fix: track every preview object-URL here and revoke them all on logout,
// alongside clearing tenant-scoped web storage. Download URLs are revoked
// inline at their call site and are intentionally NOT tracked here.

const previewUrls = new Set()

// Register a preview blob object-URL so it is revoked on logout. Returns the
// url unchanged for convenient inline use:
//   const url = trackPreviewUrl(URL.createObjectURL(blob))
export function trackPreviewUrl(url) {
  if (url) previewUrls.add(url)
  return url
}

// Revoke and forget a single tracked preview URL (e.g. on component unmount).
export function revokePreviewUrl(url) {
  if (!url) return
  try { URL.revokeObjectURL(url) } catch (_) { /* already revoked / unsupported */ }
  previewUrls.delete(url)
}

// Revoke every tracked preview URL.
export function revokePreviewUrls() {
  for (const url of previewUrls) {
    try { URL.revokeObjectURL(url) } catch (_) { /* already revoked / unsupported */ }
  }
  previewUrls.clear()
}

// Tear down all tenant-scoped client state. Call on logout BEFORE navigating to
// /login so no previous org's data lingers into the next session.
export function clearSession() {
  // 1. Revoke any preview blob object-URLs (the cross-tenant preview leak).
  revokePreviewUrls()
  // 2. Drop tenant-scoped persistent + transient web storage.
  try {
    localStorage.removeItem('token')
    // sessionStorage holds transient cross-page artefacts (deal toasts, etc.)
    // keyed to the prior session -- clear all of it on a session switch.
    sessionStorage.clear()
  } catch (_) { /* storage may be unavailable in some embeds */ }
}
