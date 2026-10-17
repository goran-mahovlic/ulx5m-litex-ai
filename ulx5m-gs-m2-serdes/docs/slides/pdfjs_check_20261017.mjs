// pdf.js (pdfjs-dist 4.10.38, legacy): render page 1, scan operator list for transparency
import { createRequire } from 'node:module'
import fs from 'node:fs'
const NM = '/home/klaudio/app/tmp/zadaci/TASK-5450_trl-faze-playvision-ai-qa/pdfjs/node_modules/'
const pdfjs = await import(NM + 'pdfjs-dist/legacy/build/pdf.mjs')
const { createCanvas } = await import(NM + '@napi-rs/canvas/index.js').catch(() => createRequire(NM)('@napi-rs/canvas'))
const [pdfPath, pngOut] = process.argv.slice(2)
const doc = await pdfjs.getDocument({ data: new Uint8Array(fs.readFileSync(pdfPath)), verbosity: 0,
  standardFontDataUrl: NM + 'pdfjs-dist/standard_fonts/' }).promise
const p = await doc.getPage(1); const vp = p.getViewport({ scale: 1 })
console.log('pdfjs', pdfjs.version, 'pages', doc.numPages, 'size', vp.width, 'x', vp.height, 'ratio', (vp.width / vp.height).toFixed(4))
const ops = await p.getOperatorList(); const O = pdfjs.OPS
let gs = 0, alpha = [], smask = 0, groups = 0
ops.fnArray.forEach((fn, i) => {
  if (fn === O.setGState) { gs++; for (const [k, v] of ops.argsArray[i][0]) {
    if ((k === 'CA' || k === 'ca') && v !== 1) alpha.push(k + '=' + v)
    if (k === 'SMask' && v) smask++ } }
  if (fn === O.beginGroup) groups++
})
console.log('setGState', gs, 'alpha!=1', alpha.length, alpha.slice(0, 5).join(','), 'SMask', smask, 'transparencyGroups', groups)
const s = 2; const v2 = p.getViewport({ scale: s }); const c = createCanvas(Math.ceil(v2.width), Math.ceil(v2.height))
await p.render({ canvasContext: c.getContext('2d'), viewport: v2 }).promise
fs.writeFileSync(pngOut, c.toBuffer('image/png'))
const tc = await p.getTextContent(); const txt = tc.items.map(x => x.str).join(' ')
console.log('text chars', txt.length, 'U+FFFD', (txt.match(/�/g) || []).length)
