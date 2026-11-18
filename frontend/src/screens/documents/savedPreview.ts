/**
 * The saved layout with each slot's text filled in, ready to show on a sheet. Only the tags the layout is written with can occur
 * (`h1 h2 h3 p ul li`, see adapters/outputs/render_html.py), but the markup is rebuilt from text nodes so nothing stored is ever run.
 * A text of several lines is several elements of the slot's kind; an empty text is a removed line.
 */
export function filledLayout(html: string, slots: Record<string, string>): string {
  const body = new DOMParser().parseFromString(html, 'text/html').body
  body.querySelectorAll('script, style, iframe, object, embed').forEach((el) => el.remove())
  body.querySelectorAll('[data-slot]').forEach((el) => {
    const lines = (slots[el.getAttribute('data-slot') ?? ''] ?? el.textContent ?? '').split('\n').map((l) => l.trim()).filter(Boolean)
    const tag = el.tagName.toLowerCase()
    el.replaceWith(...lines.map((text) => {
      const line = document.createElement(tag)
      line.className = el.className
      line.textContent = text
      return line
    }))
  })
  body.querySelectorAll('*').forEach((el) => [...el.attributes].filter((a) => a.name !== 'class').forEach((a) => el.removeAttribute(a.name)))
  return body.innerHTML
}

/** A listing link to show: an http or https address only. */
export const listingLink = (url: string | undefined): string => (url && /^https?:\/\/\S+$/i.test(url) ? url : '')
