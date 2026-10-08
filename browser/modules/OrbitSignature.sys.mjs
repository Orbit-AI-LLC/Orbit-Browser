/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/. */

/**
 * Checks an Orbit Browser update against the key releases are signed with,
 * as the Tauri updater checks the other Orbit apps' (OrbitUpdates.sys.mjs
 * uses it). Signatures are minisign's "ED" form: Ed25519 over the payload's
 * 64-byte BLAKE2b, plus a second Ed25519 signature over the first and the
 * trusted comment, which names the version. scripts/sign_update.py makes them;
 * the key and the signature are each the base64 of a minisign file, as
 * tauri.conf.json and Mission Control's feed hold them.
 *
 * Plain JavaScript, no Firefox APIs, so tests/verify_signature.mjs can run it
 * under Node against signatures the build's Python and the Tauri CLI made.
 */

// -- BLAKE2b (RFC 7693) ------------------------------------------------------------------
// 64-bit words as pairs of 32-bit ones (low, high), as JavaScript has no fast
// unsigned 64-bit arithmetic. Written for speed (a Mac update is ~150 MB,
// hashed as it downloads): one shared working state, the mixing done in locals.

const IV = new Uint32Array([
  0xf3bcc908, 0x6a09e667, 0x84caa73b, 0xbb67ae85, 0xfe94f82b, 0x3c6ef372,
  0x5f1d36f1, 0xa54ff53a, 0xade682d1, 0x510e527f, 0x2b3e6c1f, 0x9b05688c,
  0xfb41bd6b, 0x1f83d9ab, 0x137e2179, 0x5be0cd19,
]);

// The message schedule for the twelve rounds, as indices of 32-bit words.
const SIGMA = new Uint8Array(
  [
    [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15],
    [14, 10, 4, 8, 9, 15, 13, 6, 1, 12, 0, 2, 11, 7, 5, 3],
    [11, 8, 12, 0, 5, 2, 15, 13, 10, 14, 3, 6, 7, 1, 9, 4],
    [7, 9, 3, 1, 13, 12, 11, 14, 2, 6, 5, 10, 4, 0, 15, 8],
    [9, 0, 5, 7, 2, 4, 10, 15, 14, 1, 11, 12, 6, 8, 3, 13],
    [2, 12, 6, 10, 0, 11, 8, 3, 4, 13, 7, 5, 15, 14, 1, 9],
    [12, 5, 1, 15, 14, 13, 4, 10, 0, 7, 6, 3, 9, 2, 8, 11],
    [13, 11, 7, 14, 12, 1, 3, 9, 5, 0, 15, 4, 8, 6, 2, 10],
    [6, 15, 14, 9, 11, 3, 0, 8, 12, 2, 13, 7, 1, 4, 10, 5],
    [10, 2, 8, 4, 7, 6, 1, 5, 15, 11, 9, 14, 3, 12, 13, 0],
  ]
    .flat()
    .concat([0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15])
    .concat([14, 10, 4, 8, 9, 15, 13, 6, 1, 12, 0, 2, 11, 7, 5, 3])
    .map(i => i * 2)
);

const v = new Uint32Array(32);
const m = new Uint32Array(32);
const CARRY = 0x100000000;

/** The mixing function G on words a, b, c, d of v, with message words x, y. */
function mix(a, b, c, d, x, y) {
  const x0 = m[x], x1 = m[x + 1], y0 = m[y], y1 = m[y + 1];
  let a0 = v[a], a1 = v[a + 1], b0 = v[b], b1 = v[b + 1];
  let c0 = v[c], c1 = v[c + 1], d0 = v[d], d1 = v[d + 1];
  let t, lo, hi;
  // a += b + x
  t = a0 + b0;
  a1 = (a1 + b1 + ((t / CARRY) | 0)) >>> 0;
  a0 = t >>> 0;
  t = a0 + x0;
  a1 = (a1 + x1 + ((t / CARRY) | 0)) >>> 0;
  a0 = t >>> 0;
  // d = (d ^ a) >>> 32
  lo = d0 ^ a0;
  d0 = (d1 ^ a1) >>> 0;
  d1 = lo >>> 0;
  // c += d
  t = c0 + d0;
  c1 = (c1 + d1 + ((t / CARRY) | 0)) >>> 0;
  c0 = t >>> 0;
  // b = (b ^ c) >>> 24
  lo = b0 ^ c0;
  hi = b1 ^ c1;
  b0 = ((lo >>> 24) ^ (hi << 8)) >>> 0;
  b1 = ((hi >>> 24) ^ (lo << 8)) >>> 0;
  // a += b + y
  t = a0 + b0;
  a1 = (a1 + b1 + ((t / CARRY) | 0)) >>> 0;
  a0 = t >>> 0;
  t = a0 + y0;
  a1 = (a1 + y1 + ((t / CARRY) | 0)) >>> 0;
  a0 = t >>> 0;
  // d = (d ^ a) >>> 16
  lo = d0 ^ a0;
  hi = d1 ^ a1;
  d0 = ((lo >>> 16) ^ (hi << 16)) >>> 0;
  d1 = ((hi >>> 16) ^ (lo << 16)) >>> 0;
  // c += d
  t = c0 + d0;
  c1 = (c1 + d1 + ((t / CARRY) | 0)) >>> 0;
  c0 = t >>> 0;
  // b = (b ^ c) >>> 63
  lo = b0 ^ c0;
  hi = b1 ^ c1;
  b0 = (hi >>> 31) ^ (lo << 1);
  b1 = (lo >>> 31) ^ (hi << 1);
  v[a] = a0;
  v[a + 1] = a1;
  v[b] = b0;
  v[b + 1] = b1;
  v[c] = c0;
  v[c + 1] = c1;
  v[d] = d0;
  v[d + 1] = d1;
}

/** Compresses the 128-byte block at bytes[offset] into h; `counted` bytes so far. */
function compress(h, bytes, offset, counted, last) {
  for (let i = 0; i < 16; i++) {
    v[i] = h[i];
    v[i + 16] = IV[i];
  }
  v[24] ^= counted;
  v[25] ^= counted / CARRY;
  if (last) {
    v[28] = ~v[28];
    v[29] = ~v[29];
  }
  for (let i = 0; i < 32; i++) {
    const j = offset + i * 4;
    m[i] = bytes[j] ^ (bytes[j + 1] << 8) ^ (bytes[j + 2] << 16) ^ (bytes[j + 3] << 24);
  }
  for (let s = 0; s < 192; s += 16) {
    mix(0, 8, 16, 24, SIGMA[s], SIGMA[s + 1]);
    mix(2, 10, 18, 26, SIGMA[s + 2], SIGMA[s + 3]);
    mix(4, 12, 20, 28, SIGMA[s + 4], SIGMA[s + 5]);
    mix(6, 14, 22, 30, SIGMA[s + 6], SIGMA[s + 7]);
    mix(0, 10, 20, 30, SIGMA[s + 8], SIGMA[s + 9]);
    mix(2, 12, 22, 24, SIGMA[s + 10], SIGMA[s + 11]);
    mix(4, 14, 16, 26, SIGMA[s + 12], SIGMA[s + 13]);
    mix(6, 8, 18, 28, SIGMA[s + 14], SIGMA[s + 15]);
  }
  for (let i = 0; i < 16; i++) {
    h[i] ^= v[i] ^ v[i + 16];
  }
}

/** BLAKE2b-512 (unkeyed), fed in pieces: update() as the bytes come, digest() at the end. */
export class Blake2b {
  #h = new Uint32Array(IV);
  #block = new Uint8Array(128);
  #filled = 0;
  #counted = 0;

  constructor() {
    // The parameter block: a 64-byte digest, no key, fanout and depth 1.
    this.#h[0] ^= 0x01010040;
  }

  update(bytes) {
    let i = 0;
    while (i < bytes.length) {
      if (this.#filled === 128) {
        // Only now that more follows is the full block not the last one.
        this.#counted += 128;
        compress(this.#h, this.#block, 0, this.#counted, false);
        this.#filled = 0;
      }
      if (this.#filled === 0) {
        // Whole blocks straight from the input, but never the last byte
        // given: the final block is compressed differently.
        while (bytes.length - i > 128) {
          this.#counted += 128;
          compress(this.#h, bytes, i, this.#counted, false);
          i += 128;
        }
      }
      const n = Math.min(128 - this.#filled, bytes.length - i);
      this.#block.set(bytes.subarray(i, i + n), this.#filled);
      this.#filled += n;
      i += n;
    }
  }

  digest() {
    this.#counted += this.#filled;
    this.#block.fill(0, this.#filled);
    compress(this.#h, this.#block, 0, this.#counted, true);
    const out = new Uint8Array(64);
    for (let i = 0; i < 64; i++) {
      out[i] = this.#h[i >> 2] >>> (8 * (i & 3));
    }
    return out;
  }
}

// -- minisign -----------------------------------------------------------------------------

function fromBase64(text) {
  return Uint8Array.fromBase64(text.trim());
}

/** The lines of a base64'd minisign file. */
function minisignLines(encoded) {
  return new TextDecoder().decode(fromBase64(encoded)).split("\n");
}

function same(a, b) {
  return a.length === b.length && a.every((byte, i) => byte === b[i]);
}

/**
 * Checks `signature` (from Mission Control's feed) over a payload whose
 * BLAKE2b-512 is `digest`, with `publicKey`. Resolves to the trusted
 * comment's fields ({timestamp, file, version}); throws if anything is off.
 */
export async function verifyUpdateSignature(digest, signature, publicKey) {
  const keyLines = minisignLines(publicKey);
  const key = fromBase64(keyLines[1] || "");
  if (!keyLines[0].startsWith("untrusted comment:") || key.length !== 42 || key[0] !== 0x45 || key[1] !== 0x64) {
    throw new Error("The update key isn't a minisign Ed25519 key.");
  }
  const lines = minisignLines(signature);
  const prefix = "trusted comment: ";
  if (lines.length < 4 || !lines[2].startsWith(prefix)) {
    throw new Error("The update's signature isn't a minisign signature.");
  }
  const signed = fromBase64(lines[1]);
  // "ED": Ed25519 over the BLAKE2b of the payload, as the Tauri CLI signs.
  if (signed.length !== 74 || signed[0] !== 0x45 || signed[1] !== 0x44) {
    throw new Error("The update's signature isn't a prehashed Ed25519 signature.");
  }
  if (!same(signed.subarray(2, 10), key.subarray(2, 10))) {
    throw new Error("The update is signed with another key.");
  }
  const trusted = lines[2].slice(prefix.length);
  const trustedBytes = new TextEncoder().encode(trusted);
  const payloadSignature = signed.subarray(10);
  const commentSignature = new Uint8Array(64 + trustedBytes.length);
  commentSignature.set(payloadSignature);
  commentSignature.set(trustedBytes, 64);

  const ed25519 = await crypto.subtle.importKey("raw", key.subarray(10), { name: "Ed25519" }, false, ["verify"]);
  const payloadOk = await crypto.subtle.verify({ name: "Ed25519" }, ed25519, payloadSignature, digest);
  const commentOk = await crypto.subtle.verify({ name: "Ed25519" }, ed25519, fromBase64(lines[3]), commentSignature);
  if (!payloadOk || !commentOk) {
    throw new Error("The update's signature doesn't match the download.");
  }
  const fields = {};
  for (const field of trusted.split("\t")) {
    const colon = field.indexOf(":");
    if (colon > 0) {
      fields[field.slice(0, colon)] = field.slice(colon + 1);
    }
  }
  return fields;
}
