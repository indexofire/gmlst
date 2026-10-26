/**
 * Pure file input helpers used by the VisualApp Vue component.
 *
 * These functions never reference `this` and operate only on their arguments,
 * making them safe to unit test and easy to move out of the App.vue monolith.
 */

/** Maximum file size accepted by the client-side input handlers (64 MiB). */
export const MAX_FILE_SIZE = 64 * 1024 * 1024

/**
 * Read a File object as text, throwing if it exceeds the size limit.
 *
 * @param {File} file
 * @returns {Promise<string>}
 */
export async function readFileWithSizeCheck(file) {
  if (file.size > MAX_FILE_SIZE) {
    const sizeMiB = (file.size / 1024 / 1024).toFixed(1)
    const maxMiB = MAX_FILE_SIZE / 1024 / 1024
    throw new Error(`File "${file.name}" is too large (${sizeMiB} MiB). Maximum is ${maxMiB} MiB.`)
  }
  return await file.text()
}

/**
 * Parse a session restore payload from text, validating the top-level shape.
 *
 * @param {string} text
 * @returns {object}
 */
export function parseSessionPayload(text) {
  const payload = JSON.parse(text)
  if (typeof payload !== "object" || payload === null) {
    throw new Error("Session file must contain a JSON object.")
  }
  return payload
}
