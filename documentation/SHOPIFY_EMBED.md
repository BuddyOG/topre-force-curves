# Shopify embed contract

The Shopify page owns the Dome Lab header and navigation. It embeds only the
standalone EC Parts Builder:

- Shopify wrapper: <https://unrealkeyboards.com/pages/topre-ec-parts-library-builder>
- Hosted builder: <https://buddyog.github.io/topre-force-curves/dome-lab-parts.html>

The hosted path serves EC Parts Builder `lib-6.0`; this production contract is
active for that release. The embedded builder has no Home or library tabs and
no links to other tools.

The parent page and iframe have different origins. The bridge has one purpose:
establish the trusted parent and keep the iframe height synchronized. It does
not position dialogs, change either page's URL, or manage browser history.

## Trusted-origin lock

The child uses this exact parent-origin allowlist:

- `https://unrealkeyboards.com`
- `https://www.unrealkeyboards.com`
- `https://unreal-keyboards.myshopify.com`

The origin lock is established in one of two ways:

1. If `document.referrer` parses to an exact allowlisted origin, the child locks
   that origin during startup.
2. If no valid allowlisted referrer exists, the first fully validated
   `ukdl-viewport` message from `window.parent` locks its origin.

After the lock is established, even another allowlisted origin cannot replace
it for the lifetime of that document. Every message must also satisfy
`event.source === window.parent`; an origin alone is insufficient.

Wildcard origins and wildcard `postMessage` targets are forbidden.

## Messages

### Parent to child: `ukdl-viewport`

```text
{
  type: "ukdl-viewport",
  visibleTop: finite number from 0 through 10,000,000,
  viewH: finite number from 100 through 5,000
}
```

Both fields must already have JavaScript's `number` type. Numeric strings,
booleans, `NaN`, and infinities are rejected; the child must not coerce them
with `Number(...)`, `parseFloat(...)`, or an equivalent conversion.

The viewport message completes or confirms the origin handshake and requests a
fresh height report. The builder does not use `visibleTop` or `viewH` to place a
modal or move interface elements relative to the parent viewport.

### Child to parent: `ukdl-height`

```text
{
  type: "ukdl-height",
  h: finite number from 400 through 20,000
}
```

The child calculates its document height and clamps it to the inclusive
`400–20000` pixel range. It sends to the locked exact parent origin only. If no
origin has been locked, it sends nothing.

The Shopify parent accepts a height only when:

1. `event.source === iframe.contentWindow`;
2. `event.origin === "https://buddyog.github.io"`;
3. `event.data.type === "ukdl-height"`;
4. `h` already has type `number`, is finite, and is within `400–20000`.

The parent must reject, rather than coerce, an invalid height.

## Parent-side minimum

The Shopify wrapper is not owned by a file in this repository. Its Custom
Liquid or page HTML should implement this minimum contract:

```javascript
var frame = document.getElementById("ukdl-frame");
var childOrigin = "https://buddyog.github.io";

window.addEventListener("message", function (event) {
  if (event.source !== frame.contentWindow) return;
  if (event.origin !== childOrigin) return;
  if (!event.data || event.data.type !== "ukdl-height") return;
  var height = event.data.h;
  if (typeof height !== "number" || !Number.isFinite(height)) return;
  if (height < 400 || height > 20000) return;
  frame.style.height = height + "px";
});

function sendViewport() {
  var rect = frame.getBoundingClientRect();
  var visibleTop = Math.max(0, -rect.top);
  var viewH = window.innerHeight;
  if (typeof visibleTop !== "number" || !Number.isFinite(visibleTop)) return;
  if (typeof viewH !== "number" || !Number.isFinite(viewH)) return;
  frame.contentWindow.postMessage({
    type: "ukdl-viewport",
    visibleTop: visibleTop,
    viewH: viewH
  }, childOrigin);
}

frame.addEventListener("load", sendViewport);
window.addEventListener("scroll", sendViewport, { passive: true });
window.addEventListener("resize", sendViewport);
sendViewport();
```

The production wrapper may retain its existing layout CSS and a modest
handshake retry timer. A timer does not weaken the source-window, exact-origin,
type, or bounds checks.

## Lifecycle

1. The parent locates the iframe and installs its message listener.
2. An allowlisted referrer may let the child lock the parent and report its
   initial height immediately.
3. On iframe load, and once during setup, the parent sends `ukdl-viewport` to
   the exact GitHub Pages origin. This supplies the fallback origin lock when a
   valid referrer was unavailable.
4. `ResizeObserver`, load, and builder layout changes request later bounded
   height reports from the child.
5. Parent scroll and resize events may repeat the viewport handshake. They do
   not change the locked origin and do not reposition builder dialogs.

Shopify theme preview must be tested to establish its actual immediate parent
origin. Do not add a wildcard or broad `*.myshopify.com` rule to make an
unrecognized preview origin work.

## History and navigation boundary

The embedded builder must not call `history.pushState`,
`history.replaceState`, or mutate `location.hash` for chooser or detail state.
It must not emit or accept a modal-placement message. Shopify owns the page URL
and navigation; the builder keeps transient UI state inside the iframe.

## Acceptance checks

- The builder loads without an iframe scrollbar.
- Height follows row, chooser, filter, disclosure, and details-dialog changes.
- A valid allowlisted referrer establishes the lock before the first message.
- Without a usable referrer, the first valid parent viewport message establishes
  the lock.
- A later message from a different origin is rejected even if that origin is
  also allowlisted.
- A message from a sibling iframe is rejected.
- Numeric strings, booleans, `NaN`, infinities, negative dimensions, heights
  below 400, and heights above 20,000 are rejected.
- Child height messages use the locked exact target origin, never `"*"`.
- No viewport message moves a dialog, and chooser/detail actions do not change
  the browser history or URL.
- The standalone GitHub Pages builder remains usable when it is not framed.
