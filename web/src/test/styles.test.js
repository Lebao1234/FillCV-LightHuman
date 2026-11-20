// Kiểm thử CSS: mọi biến var(--x) phải có trong tokens.css, không có mã màu viết cứng, không còn style trực tiếp
import { readFileSync, readdirSync, statSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { describe, it, expect } from 'vitest'

const SRC = join(dirname(fileURLToPath(import.meta.url)), '..')

// Đọc đệ quy mọi file có đuôi cho trước
function listFiles(dir, exts) {
  return readdirSync(dir).flatMap((name) => {
    const p = join(dir, name)
    if (name === 'test' || name === 'node_modules') return []
    return statSync(p).isDirectory() ? listFiles(p, exts) : exts.some((e) => p.endsWith(e)) ? [p] : []
  })
}

const tokens = readFileSync(join(SRC, 'tokens.css'), 'utf8')
const defined = new Set([...tokens.matchAll(/(--[a-z0-9-]+)\s*:/g)].map((m) => m[1]))
const cssFiles = listFiles(SRC, ['.css']).filter((p) => !p.endsWith('tokens.css') && !p.endsWith('index.css'))
const jsxFiles = listFiles(SRC, ['.jsx'])

describe('Design tokens trong CSS', () => {
  // Mọi var(--x) dùng trong CSS/JSX phải được định nghĩa trong tokens.css
  it('không dùng token chưa định nghĩa', () => {
    const missing = []
    for (const f of [...cssFiles, ...jsxFiles]) {
      const text = readFileSync(f, 'utf8')
      for (const m of text.matchAll(/var\((--[a-z0-9-]+)/g)) {
        if (!defined.has(m[1])) missing.push(`${f.replace(SRC, '')}: ${m[1]}`)
      }
    }
    expect(missing).toEqual([])
  })

  // Màu chỉ được khai báo trong tokens.css
  it('không viết cứng mã màu trong CSS thành phần', () => {
    const bad = []
    for (const f of cssFiles) {
      const text = readFileSync(f, 'utf8')
      for (const m of text.matchAll(/#[0-9a-fA-F]{3,8}\b|rgba?\(/g)) bad.push(`${f.replace(SRC, '')}: ${m[0]}`)
    }
    expect(bad).toEqual([])
  })

  // Style đặt trực tiếp trong JSX đi vòng qua hệ thống token và utility
  it('không còn style={{...}} trong JSX', () => {
    const bad = jsxFiles.filter((f) => /style=\{\{/.test(readFileSync(f, 'utf8')))
    expect(bad.map((f) => f.replace(SRC, ''))).toEqual([])
  })

  // Khai báo CSS hỏng (thiếu tên thuộc tính hoặc lẫn ký tự điều khiển) sẽ bị bỏ qua âm thầm khi build
  it('không có khai báo thiếu tên thuộc tính hoặc ký tự điều khiển', () => {
    const bad = []
    for (const f of cssFiles) {
      readFileSync(f, 'utf8')
        .split(/\r?\n/)
        .forEach((line, i) => {
          // eslint-disable-next-line no-control-regex
          const hasControlChar = /[\x00-\x08\x0e-\x1f]/.test(line)
          if (/^\s*:\s/.test(line) || hasControlChar) bad.push(`${f.replace(SRC, '')}:${i + 1}`)
        })
    }
    expect(bad).toEqual([])
  })

  // Chỉ một họ font: không còn font mono
  it('chỉ dùng một họ font (Be Vietnam Pro)', () => {
    expect(tokens).not.toMatch(/JetBrains|font-mono/)
  })
})
