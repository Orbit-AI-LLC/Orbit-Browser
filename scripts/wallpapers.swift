// Orbit Browser's new tab wallpapers.
//
// Space in Orbit Browser's colours: a blue-black sky, Orbit teal (#3fe0cf to
// #0a7f8c, the window's accent), and the family's orbit, an ellipse tilted 22° to
// rise to the right with a moon riding it at the top right, passing behind
// the planet above and in front of it below (scripts/orbitmark.swift). Every
// scene is drawn here from code with fixed seeds, so a run makes the same
// images each time. Edit a scene and run it again; never edit the outputs.
//
// Build and run (macOS):
//
//   xcrun swiftc -O -o /tmp/wallpapers scripts/wallpapers.swift
//   /tmp/wallpapers write branding/content/wallpapers            every scene
//   /tmp/wallpapers write branding/content/wallpapers horizon    one scene
//   /tmp/wallpapers preview /tmp/previews [scene…]               1600 × 900 PNGs, quickly
//
// write makes <scene>.jpg (3840 × 2160; the new tab covers the window with
// it) and <scene>-thumb.jpg (480 × 270, for the wallpaper picker). The new
// tab lists them from ORBIT_WALLPAPERS in scripts/omni_patches.py, which names
// each one and says where it's anchored when the window crops it. They're
// JPEG because ImageIO writes an AVIF over 512 pixels as a grid of tiles,
// which Firefox won't decode.
import CoreGraphics
import Foundation
import ImageIO
import UniformTypeIdentifiers

// MARK: - Colour, in linear light

struct C {
    var r: Float, g: Float, b: Float
    init(_ r: Float, _ g: Float, _ b: Float) { self.r = r; self.g = g; self.b = b }
    init(_ v: Float) { self.init(v, v, v) }
    static let black = C(0)
    static func + (a: C, b: C) -> C { C(a.r + b.r, a.g + b.g, a.b + b.b) }
    static func * (a: C, k: Float) -> C { C(a.r * k, a.g * k, a.b * k) }
    static func * (a: C, b: C) -> C { C(a.r * b.r, a.g * b.g, a.b * b.b) }
    static func += (a: inout C, b: C) { a = a + b }
}

func mix(_ a: C, _ b: C, _ t: Float) -> C { a * (1 - t) + b * t }
func clamp(_ x: Float, _ lo: Float = 0, _ hi: Float = 1) -> Float { min(max(x, lo), hi) }
/// A bell curve: 1 at 0, falling away on either side.
func bell(_ x: Float) -> Float { exp(-x * x) }
func smoothstep(_ a: Float, _ b: Float, _ x: Float) -> Float {
    let t = clamp((x - a) / (b - a))
    return t * t * (3 - 2 * t)
}

func linear(_ v: Float) -> Float { v <= 0.04045 ? v / 12.92 : pow((v + 0.055) / 1.055, 2.4) }
func encoded(_ v: Float) -> Float { v <= 0.0031308 ? v * 12.92 : 1.055 * pow(v, 1 / 2.4) - 0.055 }
/// An sRGB colour as CSS writes it, in linear light.
func hex(_ s: String) -> C {
    let n = UInt32(s.dropFirst(), radix: 16)!
    return C(linear(Float(n >> 16 & 255) / 255), linear(Float(n >> 8 & 255) / 255), linear(Float(n & 255) / 255))
}

/// The Orbit Browser mark's tile, light end and dark end.
let aqua = hex("#3fe0cf"), teal = hex("#0a7f8c")

/// Colours at stops along 0…1.
struct Ramp {
    let stops: [(Float, C)]
    init(_ stops: [(Float, String)]) { self.stops = stops.map { ($0.0, hex($0.1)) } }
    func at(_ t: Float) -> C {
        if t <= stops[0].0 { return stops[0].1 }
        for i in 1..<stops.count where t <= stops[i].0 {
            let (a, ca) = stops[i - 1], (b, cb) = stops[i]
            return mix(ca, cb, (t - a) / (b - a))
        }
        return stops[stops.count - 1].1
    }
}

// MARK: - Vectors: x right, y down, z toward the viewer

struct V {
    var x: Float, y: Float, z: Float = 0
    static func + (a: V, b: V) -> V { V(x: a.x + b.x, y: a.y + b.y, z: a.z + b.z) }
    static func - (a: V, b: V) -> V { V(x: a.x - b.x, y: a.y - b.y, z: a.z - b.z) }
    static func * (a: V, k: Float) -> V { V(x: a.x * k, y: a.y * k, z: a.z * k) }
    func dot(_ b: V) -> Float { x * b.x + y * b.y + z * b.z }
    func cross(_ b: V) -> V { V(x: y * b.z - z * b.y, y: z * b.x - x * b.z, z: x * b.y - y * b.x) }
    var length: Float { dot(self).squareRoot() }
    var unit: V { self * (1 / length) }
}

func p(_ x: Float, _ y: Float) -> V { V(x: x, y: y) }
let D = Float.pi / 180

// MARK: - Randomness and noise, from seeds

struct RNG {
    var state: UInt64
    init(_ seed: UInt64) { state = seed }
    mutating func next() -> UInt64 {
        state &+= 0x9E37_79B9_7F4A_7C15
        var z = state
        z = (z ^ (z >> 30)) &* 0xBF58_476D_1CE4_E5B9
        z = (z ^ (z >> 27)) &* 0x94D0_49BB_1331_11EB
        return z ^ (z >> 31)
    }
    mutating func float() -> Float { Float(next() >> 40) / Float(1 << 24) }
}

/// Gradient noise (Perlin's), about -1…1, and sums of it.
struct Noise {
    let perm: [Int]
    init(_ seed: UInt64) {
        var rng = RNG(seed), a = Array(0..<256)
        for i in stride(from: 255, to: 0, by: -1) { a.swapAt(i, Int(rng.next() % UInt64(i + 1))) }
        perm = a + a
    }
    private func grad(_ h: Int, _ x: Float, _ y: Float) -> Float {
        switch h & 7 {
        case 0: return x + y
        case 1: return -x + y
        case 2: return x - y
        case 3: return -x - y
        case 4: return x
        case 5: return -x
        case 6: return y
        default: return -y
        }
    }
    func callAsFunction(_ x: Float, _ y: Float) -> Float {
        let xf = x.rounded(.down), yf = y.rounded(.down)
        let xi = Int(xf) & 255, yi = Int(yf) & 255
        let x0 = x - xf, y0 = y - yf
        let u = x0 * x0 * x0 * (x0 * (x0 * 6 - 15) + 10), v = y0 * y0 * y0 * (y0 * (y0 * 6 - 15) + 10)
        let a = perm[xi] + yi, b = perm[xi + 1] + yi
        let bottom = grad(perm[a], x0, y0) + u * (grad(perm[b], x0 - 1, y0) - grad(perm[a], x0, y0))
        let top = grad(perm[a + 1], x0, y0 - 1) + u * (grad(perm[b + 1], x0 - 1, y0 - 1) - grad(perm[a + 1], x0, y0 - 1))
        return bottom + v * (top - bottom)
    }
    /// Octaves of noise, each twice as fine and turned so their grids don't line up.
    func fbm(_ x: Float, _ y: Float, _ octaves: Int, gain: Float = 0.5) -> Float {
        var sum: Float = 0, amp: Float = 1, norm: Float = 0, x = x, y = y
        for _ in 0..<octaves {
            sum += amp * self(x, y)
            norm += amp
            amp *= gain
            (x, y) = (1.6 * x - 1.2 * y + 17.3, 1.2 * x + 1.6 * y - 9.1)
        }
        return sum / norm
    }
    /// Sharp crests where the noise crosses zero: filaments and dust lanes.
    func ridged(_ x: Float, _ y: Float, _ octaves: Int) -> Float {
        var sum: Float = 0, amp: Float = 1, norm: Float = 0, x = x, y = y
        for _ in 0..<octaves {
            let n = 1 - abs(self(x, y))
            sum += amp * n * n
            norm += amp
            amp *= 0.5
            (x, y) = (1.6 * x - 1.2 * y + 5.7, 1.2 * x + 1.6 * y + 3.3)
        }
        return sum / norm
    }
}

// MARK: - The canvas, in scene units: 1 high, (0, 0) in the middle

final class Canvas {
    let w: Int, h: Int
    var px: [C]
    init(_ w: Int, _ h: Int) {
        self.w = w; self.h = h
        px = Array(repeating: .black, count: w * h)
    }
    var aspect: Float { Float(w) / Float(h) }
    /// One pixel, in scene units.
    var pixel: Float { 1 / Float(h) }
    /// This canvas's pixels per 4K pixel; star sizes are given at 4K.
    var scale: Float { Float(h) / 2160 }

    /// Sets every pixel to f(point, colour so far), rows in parallel.
    func shade(_ f: (V, C) -> C) {
        let w = self.w, h = self.h
        px.withUnsafeMutableBufferPointer { buffer in
            let base = buffer.baseAddress!
            DispatchQueue.concurrentPerform(iterations: h) { y in
                let v = (Float(y) + 0.5 - Float(h) / 2) / Float(h)
                for x in 0..<w {
                    let u = (Float(x) + 0.5 - Float(w) / 2) / Float(h)
                    base[y * w + x] = f(V(x: u, y: v), base[y * w + x])
                }
            }
        }
    }

    /// Adds a round Gaussian of light, sigma in pixels.
    func glow(at q: V, sigma: Float, _ colour: C) {
        let cx = q.x * Float(h) + Float(w) / 2 - 0.5, cy = q.y * Float(h) + Float(h) / 2 - 0.5
        let reach = Int((sigma * 3.5).rounded(.up))
        let x0 = max(0, Int(cx) - reach), x1 = min(w - 1, Int(cx) + reach)
        let y0 = max(0, Int(cy) - reach), y1 = min(h - 1, Int(cy) + reach)
        guard x0 <= x1, y0 <= y1 else { return }
        let k = -1 / (2 * sigma * sigma)
        for y in y0...y1 {
            let dy = Float(y) - cy
            for x in x0...x1 {
                let dx = Float(x) - cx
                px[y * w + x] += colour * exp((dx * dx + dy * dy) * k)
            }
        }
    }
}

// MARK: - Stars

struct Star { var at: V; var brightness: Float; var size: Float; var tint: C }

/// Stars scattered where density (0…1) lets them be: most faint, a few bright.
func scatter(_ count: Int, seed: UInt64, aspect: Float, brightest: Float = 1.6,
             density: (V) -> Float = { _ in 1 }) -> [Star] {
    var rng = RNG(seed), out: [Star] = []
    let tints = [C(1), C(1), hex("#dce9ff"), hex("#cdfaf3"), hex("#ffeedd")]
    var tries = 0
    while out.count < count && tries < count * 200 {
        tries += 1
        let at = p((rng.float() - 0.5) * aspect, rng.float() - 0.5)
        if rng.float() > density(at) { continue }
        let t = rng.float()
        out.append(Star(at: at, brightness: 0.006 + 0.12 * pow(t, 4) + brightest * pow(t, 40), size: 0.55 + 1.1 * pow(t, 12),
                        tint: tints[Int(rng.next() % UInt64(tints.count))]))
    }
    return out
}

/// Draws stars, dimmed by visible (0 behind a planet, 1 in open sky).
func draw(_ stars: [Star], on c: Canvas, gain: Float = 1, visible: (V) -> Float = { _ in 1 }) {
    for s in stars {
        let seen = visible(s.at)
        if seen <= 0 { continue }
        // A star finer than a pixel keeps its light, spread over the pixel.
        let sigma = max(0.5, s.size * c.scale)
        let energy = pow(s.size * c.scale / sigma, 2)
        c.glow(at: s.at, sigma: sigma, s.tint * (s.brightness * energy * gain * seen))
        // Only the brightest few get a halo.
        if s.brightness > 1 {
            c.glow(at: s.at, sigma: (3 + 4 * s.brightness) * c.scale, mix(s.tint, aqua, 0.35) * (0.012 * s.brightness * gain * seen))
        }
    }
}

// MARK: - Bodies

/// Pixels' coverage of a disc, smoothed over one pixel at its edge.
func coverage(_ q: V, _ centre: V, _ r: Float, _ pixel: Float) -> Float {
    clamp((r - (q - centre).length) / pixel + 0.5)
}

/// The family orbit: an ellipse tilted so it rises to the right, its near half
/// (below its long axis) in front of what it circles.
struct Orbit {
    var c: V, rx: Float, ry: Float, tilt: Float = -22
    init(_ c: V, _ rx: Float, ratio: Float = 3.28, tilt: Float = -22) {
        self.c = c; self.rx = rx; ry = rx / ratio; self.tilt = tilt
    }
    /// The point at angle t (degrees): 0 is the right end, negative the far side.
    func at(_ t: Float) -> V {
        let x = rx * cos(t * D), y = ry * sin(t * D), a = tilt * D
        return c + p(x * cos(a) - y * sin(a), x * sin(a) + y * cos(a))
    }
    /// A point in the orbit's own frame: x along its long axis, y toward its near side.
    func local(_ q: V) -> V {
        let d = q - c, a = -tilt * D
        return p(d.x * cos(a) - d.y * sin(a), d.x * sin(a) + d.y * cos(a))
    }
    /// About how far q is from the line, and whether it's on the near side.
    func distance(_ q: V) -> (Float, near: Bool) {
        let l = local(q)
        let f = (l.x * l.x) / (rx * rx) + (l.y * l.y) / (ry * ry) - 1
        let gx = 2 * l.x / (rx * rx), gy = 2 * l.y / (ry * ry)
        return (abs(f) / max((gx * gx + gy * gy).squareRoot(), 1e-6), l.y > 0)
    }
    /// The tilted plane's pole, for bands that lie along the orbit.
    var pole: V {
        let k = ry / rx, a = tilt * D, up = -(1 - k * k).squareRoot()
        return V(x: -up * sin(a), y: up * cos(a), z: k)
    }
    var axis: V { V(x: cos(tilt * D), y: sin(tilt * D), z: 0) }
}

/// A lit sphere: what its surface shows at a normal, and its air.
struct Planet {
    var c: V, r: Float
    var light: V
    var surface: (V) -> C
    var air: C = aqua
    var airStrength: Float = 1
    var airHeight: Float = 0.035
    var night = hex("#03121a") * 0.5

    /// The planet over what's behind it: (colour, how much of the pixel it covers).
    func shade(_ q: V, over behind: C, pixel: Float) -> (C, Float) {
        let d = q - c, dist = d.length / r
        let cov = clamp((r - d.length) / pixel + 0.5)
        // How lit the limb is in this direction, for the air's glow.
        let toward = dist > 0 ? p(d.x / d.length, d.y / d.length) : p(0, 0)
        let litSide = smoothstep(-0.55, 0.85, toward.dot(p(light.x, light.y).unit))
        var outside = behind
        if dist > 0.98 {
            let h = max(0, dist - 1)
            let halo = exp(-h / airHeight) * 0.55 + exp(-h / (airHeight * 7)) * 0.05
            outside += air * (halo * (0.06 + 0.94 * litSide) * airStrength)
        }
        guard cov > 0 else { return (outside, 0) }
        let rr = min(dist, 1)
        let n = V(x: d.x / r, y: d.y / r, z: (1 - rr * rr).squareRoot())
        let ndl = n.dot(light)
        let lit = smoothstep(-0.1, 0.4, ndl) * (0.2 + 0.8 * max(ndl, 0))
        var colour = surface(n) * (lit * pow(n.z, 0.2)) + night
        let fresnel = pow(1 - n.z, 2.2)
        colour += air * (fresnel * (0.05 + 0.75 * smoothstep(-0.35, 0.6, ndl)) * airStrength)
        return (mix(outside, colour, cov), cov)
    }
}

// MARK: - Skies

/// Deep space: blue-black, a little lighter toward a point.
func space(_ q: V, light: V, reach: Float = 1.1) -> C {
    let t = smoothstep(reach, 0, (q - light).length)
    return mix(hex("#020509"), hex("#0a1f2c"), t * t)
}

/// A faint haze of gas, to keep a dark sky from being flat.
func haze(_ n: Noise, _ q: V, scale: Float = 1.4) -> Float {
    let t = clamp(n.fbm(q.x * scale, q.y * scale, 5) + 0.5)
    return t * t
}

// MARK: - The scenes

typealias Scene = (Canvas) -> Void

/// A teal planet like the mark's: banded, lit from the top left, circled by
/// its orbit with the moon riding it at the top right.
func planetScene(_ c: Canvas) {
    let px = c.pixel, gas = Noise(11), dust = Noise(12)
    let centre = p(0.42, 0.06), radius: Float = 0.235
    let orbit = Orbit(centre, 0.44)
    let moonAt = orbit.at(-12), moonR: Float = 0.034
    let light = V(x: -0.62, y: -0.48, z: 0.62).unit
    let pole = orbit.pole, axis = orbit.axis
    let bands = Ramp([(0, "#0a5f6b"), (0.2, "#0b7f8a"), (0.38, "#21b5ad"), (0.5, "#5fe6d6"),
                      (0.62, "#2cc2b8"), (0.8, "#0d8a92"), (1, "#0a5f6b")])
    let planet = Planet(c: centre, r: radius, light: light, surface: { n in
        let lat = asin(clamp(n.dot(pole), -1, 1))
        let along = n.dot(axis)
        let swirl = gas.fbm(along * 2.4, lat * 7, 5) * 0.4
        let t = lat * 2.1 + swirl + 0.5
        return bands.at(t - t.rounded(.down)) * 1.05
    })
    let moon = Planet(c: moonAt, r: moonR, light: light, surface: { n in
        hex("#cfe6e3") * (0.82 + 0.3 * dust.fbm(n.x * 5, n.y * 5, 4))
    }, airStrength: 0.25, airHeight: 0.05)
    let sky = Noise(13)

    c.shade { q, _ in
        var colour = space(q, light: p(-0.9, -0.6), reach: 1.6)
        colour += mix(hex("#1a2a6b"), teal, 0.6) * (0.035 * haze(sky, q - p(0.3, 0)) * smoothstep(0.2, -0.9, q.x))
        let (line, near) = orbit.distance(q)
        let w: Float = 0.0011
        // The orbit stops short of the moon, as in the mark.
        let clear = smoothstep(moonR * 1.5, moonR * 2.4, (q - moonAt).length)
        let ring = (bell(line / w) * 0.75 + bell(line / (w * 7)) * 0.06) * clear
        let ringColour = mix(aqua, C(1), 0.25)
        // Behind the planet above its middle, in front of it below.
        if !near { colour += ringColour * ring }
        var (body, cov) = planet.shade(q, over: colour, pixel: px)
        if near && cov > 0 {
            // The mark's clear gap where the orbit crosses in front.
            let gap = smoothstep(w * 2.2, w * 4.5, line)
            body = mix(colour, body, cov * gap)
            cov *= gap
        }
        colour = body
        if near { colour += ringColour * ring }
        let (withMoon, _) = moon.shade(q, over: colour, pixel: px)
        return withMoon
    }
    let behind = { (q: V) -> Float in
        (1 - coverage(q, centre, radius, px)) * (1 - coverage(q, moonAt, moonR, px))
            * smoothstep(0.0, 0.08, (q - centre).length - radius)
    }
    draw(scatter(Int(5200 * c.aspect / 1.78), seed: 14, aspect: c.aspect), on: c, visible: behind)
}

/// A teal and indigo nebula drifting across the stars, its bright heart at
/// the left.
func nebulaScene(_ c: Canvas) {
    let warp = Noise(21), gas = Noise(22), lanes = Noise(23), fog = Noise(24)
    let glow = Ramp([(0, "#000000"), (0.12, "#120f33"), (0.3, "#16245a"), (0.48, "#0a5b72"),
                     (0.66, "#0e9b9c"), (0.82, "#3fe0cf"), (1, "#e2fffa")])
    func spine(_ q: V) -> Float {
        let centreLine = -0.36 * q.x + 0.04 + 0.1 * sin(q.x * 2.6 + 0.6)
        return abs(q.y - centreLine) * 0.94
    }
    func density(_ q: V) -> Float {
        let wx = warp.fbm(q.x * 1.5 + 3.1, q.y * 1.5 - 1.7, 4), wy = warp.fbm(q.x * 1.5 - 4.3, q.y * 1.5 + 2.9, 4)
        let w = p(q.x + 0.5 * wx, q.y + 0.5 * wy)
        let band = bell(spine(w) / 0.24)
        let heart = exp(-((q - p(-0.5, 0.17)).dot(q - p(-0.5, 0.17))) / 0.06)
        let far = exp(-((q - p(0.62, -0.28)).dot(q - p(0.62, -0.28))) / 0.07)
        let shape = band * (0.4 + 0.6 * heart + 0.3 * far)
        let cloud = clamp(gas.fbm(w.x * 2.4, w.y * 2.4, 7) * 1.1 + 0.5)
        let wisps = pow(gas.ridged(w.x * 4 + 2, w.y * 4, 5), 3)
        return shape * (0.2 + 0.8 * cloud * cloud) * (0.7 + 0.6 * wisps)
    }
    c.shade { q, _ in
        let d = density(q)
        let dust = smoothstep(0.62, 0.9, lanes.ridged(q.x * 3.2 + 1, q.y * 3.2, 5)) * smoothstep(0.05, 0.35, d)
        var colour = space(q, light: p(-0.5, 0.17), reach: 1.3)
        colour += hex("#1c1650") * (0.05 * haze(fog, q, scale: 1.1))
        colour += mix(hex("#1d1a5a"), teal, 0.35) * (0.05 * bell(spine(q) / 0.4))
        colour += glow.at(clamp(d * 1.35)) * (0.85 * (1 - 0.75 * dust))
        return colour
    }
    let field = scatter(Int(7000 * c.aspect / 1.78), seed: 25, aspect: c.aspect) { q in
        0.35 + 0.65 * smoothstep(0.0, 0.5, density(q))
    }
    draw(field, on: c)
    // Young stars in the bright heart.
    for (at, b) in [(p(-0.53, 0.2), 1.0), (p(-0.41, 0.12), 0.7), (p(-0.6, 0.08), 0.55), (p(0.58, -0.27), 0.5)] as [(V, Float)] {
        c.glow(at: at, sigma: 1.4 * c.scale, C(1) * (2.5 * b))
        c.glow(at: at, sigma: 9 * c.scale, mix(aqua, C(1), 0.5) * (0.25 * b))
        c.glow(at: at, sigma: 60 * c.scale, aqua * (0.03 * b))
    }
}

/// The edge of a planet at night, its air lit teal by a sun coming up over
/// it, and the stars above.
func horizonScene(_ c: Canvas) {
    let px = c.pixel, clouds = Noise(31), milky = Noise(32), fog = Noise(33)
    let centre = p(0, 2.62), radius: Float = 2.3
    let sunAngle = asin(0.42 / radius)
    let sun = centre + p(sin(sunAngle), -cos(sunAngle)) * (radius + 0.002)
    func height(_ q: V) -> (Float, Float) {
        let d = q - centre
        let angle = atan2(d.x, -d.y)
        return (d.length - radius, abs(angle - sunAngle) * radius)
    }
    func milkyWay(_ q: V) -> Float {
        let across = (q.y + 0.42 + 0.2 * q.x) / 1.02
        return bell(across / 0.11) * smoothstep(-0.3, 0.6, milky.fbm(q.x * 3, q.y * 3, 6) + 0.25)
    }
    c.shade { q, _ in
        let (h, a) = height(q)
        let nearSun = bell(a / 0.32), atSun = bell(a / 0.07)
        var colour = mix(hex("#02050a"), hex("#071a26"), smoothstep(-0.5, 0.35, q.y))
        colour += mix(hex("#2a1d6b"), teal, 0.5) * (0.06 * milkyWay(q))
        colour += hex("#14204f") * (0.03 * haze(fog, q))
        if h > 0 {
            let air = exp(-h / 0.009) * (0.1 + 1.0 * nearSun + 2.6 * atSun)
            let upper = exp(-h / 0.07) * (0.02 + 0.12 * bell(a / 0.7))
            colour += mix(teal, aqua, nearSun) * air + mix(teal, C(1), atSun * 0.7) * (air * 0.3 * atSun)
            colour += teal * upper
        } else {
            let depth = -h
            let rim = exp(-depth / 0.0035) * (0.06 + 0.9 * nearSun + 1.6 * atSun)
            let cloud = smoothstep(-0.1, 0.5, clouds.fbm(q.x * 7, q.y * 24, 6))
            let dawn = exp(-depth / 0.05) * bell(a / 0.45) * cloud * 0.16
            let ground = mix(hex("#020a0f"), hex("#04141b"), exp(-depth / 0.2))
            let surface = ground + mix(teal, aqua, nearSun) * rim + teal * dawn
            colour = mix(colour, surface, clamp(-h / px + 0.5))
        }
        let r = (q - sun).length
        colour += mix(aqua, C(1), 0.6) * (0.45 * bell(r / 0.03)) + teal * (0.1 * exp(-r / 0.2))
        return colour
    }
    // The sun's bright edge, just risen over the limb.
    c.glow(at: sun, sigma: 7 * c.scale, C(1) * 4)
    c.glow(at: sun, sigma: 22 * c.scale, mix(aqua, C(1), 0.7) * 0.6)
    let field = scatter(Int(6000 * c.aspect / 1.78), seed: 34, aspect: c.aspect) { q in 0.4 + 0.6 * milkyWay(q) }
    draw(field, on: c) { q in
        let (h, _) = height(q)
        return smoothstep(0.0, 0.1, h) * (1 - exp(-(q - sun).length / 0.12))
    }
}

/// A planet in front of its star: a dark disc ringed in teal light, a bead of
/// sunlight at its top right.
func eclipseScene(_ c: Canvas) {
    let px = c.pixel, rays = Noise(41), fog = Noise(42)
    let centre = p(0.5, -0.1), radius: Float = 0.13
    let corona = Ramp([(0, "#e8fffb"), (0.25, "#7ff0e2"), (0.55, "#3fe0cf"), (1, "#0a7f8c")])
    c.shade { q, _ in
        let d = q - centre, dist = d.length / radius
        var colour = space(q, light: centre, reach: 1.4)
        colour += hex("#141b4d") * (0.04 * haze(fog, q, scale: 1.2))
        if dist > 0.97 {
            let dir = p(d.x / d.length, d.y / d.length)
            let out = log(max(dist, 1))
            let streak = rays.fbm(dir.x * 3.5 + dir.y * out * 1.5, dir.y * 3.5 - dir.x * out * 1.5, 5)
            let fine = rays.fbm(dir.x * 14 + 40, dir.y * 14, 3)
            let s = clamp(0.45 + 1.1 * streak + 0.35 * fine, 0.05, 2)
            let h = max(dist - 1, 0)
            let light = (pow(max(dist, 1), -8) * 0.9 + exp(-h / 0.14) * 0.45 + exp(-h / 0.7) * 0.07) * s
            colour += corona.at(clamp(h / 1.2)) * light
            colour += mix(aqua, C(1), 0.6) * (1.4 * bell((dist - 1) * radius / 0.0016))
        }
        let cov = clamp((radius - d.length) / px + 0.5)
        return mix(colour, hex("#010406") + teal * 0.004, cov)
    }
    let bead = centre + p(cos(-48 * D), sin(-48 * D)) * radius
    c.glow(at: bead, sigma: 4 * c.scale, C(1) * 5)
    c.glow(at: bead, sigma: 16 * c.scale, mix(aqua, C(1), 0.7) * 0.8)
    c.glow(at: bead, sigma: 45 * c.scale, aqua * 0.08)
    draw(scatter(Int(4800 * c.aspect / 1.78), seed: 43, aspect: c.aspect), on: c) { q in
        let dist = (q - centre).length / radius
        return smoothstep(1.0, 1.02, dist) * smoothstep(1.2, 3.5, dist)
    }
}

/// A comet high on the right, its teal tail streaming away across the sky.
func cometScene(_ c: Canvas) {
    let streaks = Noise(51), fog = Noise(52)
    let head = p(0.56, -0.24)
    let tail = p(-1, 0.36).unit, side = p(-tail.y, tail.x)
    let dustTail = p(-1, 0.62).unit
    c.shade { q, _ in
        var colour = space(q, light: head, reach: 1.5)
        colour += mix(hex("#1a1f5c"), teal, 0.3) * (0.04 * haze(fog, q, scale: 1.2))
        let d = q - head
        let along = d.dot(tail), across = d.dot(side)
        if along > 0 {
            let width = 0.008 + 0.06 * along
            let ray = 0.55 + 0.45 * streaks.fbm(along * 1.3, across / width * 2.2, 4)
                + 0.3 * streaks.fbm(along * 0.6 + 9, across / width * 7, 3)
            let ion = bell(across / width) * exp(-along / 0.75) * max(ray, 0)
            colour += mix(teal, aqua, exp(-along / 0.4)) * (0.55 * ion)
        }
        let alongDust = d.dot(dustTail), acrossDust = d.dot(p(-dustTail.y, dustTail.x)) + 0.12 * alongDust * alongDust
        if alongDust > 0 {
            let width = 0.008 + 0.05 * alongDust
            let fan = bell(acrossDust / width) * exp(-alongDust / 0.25)
            colour += mix(C(1), aqua, 0.2) * (0.1 * fan)
        }
        let r = d.length
        colour += mix(aqua, C(1), 0.5) * (0.5 * bell(r / 0.016) + 0.06 * exp(-r / 0.08))
        return colour
    }
    c.glow(at: head, sigma: 2.5 * c.scale, C(1) * 6)
    c.glow(at: head, sigma: 10 * c.scale, mix(aqua, C(1), 0.6) * 0.9)
    draw(scatter(Int(5600 * c.aspect / 1.78), seed: 53, aspect: c.aspect), on: c) { q in
        smoothstep(0.02, 0.12, (q - head).length)
    }
}

/// The mark drawn out: a teal planet in its gradient and the orbits around
/// it, flat, like the mark. Dark, or light.
func orbitsScene(dark: Bool) -> Scene {
    { c in
        let px = c.pixel
        let centre = p(-0.5, 0.3), radius: Float = 0.11
        let orbits = [0.26, 0.42, 0.62, 0.88, 1.2, 1.6].map { Orbit(centre, $0) }
        let moons: [(Int, Float, Float)] = [(0, -12, 0.022), (2, 196, 0.015), (3, 32, 0.024), (5, -38, 0.018)]
        let moonDiscs = moons.map { (orbits[$0.0].at($0.1), $0.2) }
        let w: Float = dark ? 0.0012 : 0.0014, gap: Float = 0.0075
        let ink = dark ? aqua : hex("#0a95a0")
        // The mark's gradient: from the top left, light to dark.
        let toward = p(0.5, 1).unit
        func fill(_ q: V, _ at: V, _ r: Float) -> C {
            let t = clamp(0.5 + (q - at).dot(toward) / (2 * r))
            return mix(hex("#3fe0cf"), hex("#0a7f8c"), t)
        }
        c.shade { q, _ in
            let fromCentre = (q - centre).length
            var colour = dark
                ? mix(hex("#03080e"), hex("#0b2230"), smoothstep(1.6, 0, fromCentre))
                : mix(hex("#e1f2f0"), hex("#f8fdfc"), smoothstep(1.7, 0, fromCentre))
            if dark { colour += aqua * (0.05 * exp(-max(fromCentre - radius, 0) / 0.09)) }
            // The planet, with a clear gap round whatever crosses in front of it.
            var planet = coverage(q, centre, radius, px)
            var lines: Float = 0
            for (i, orbit) in orbits.enumerated() {
                let (d, near) = orbit.distance(q)
                var line = clamp((w - d) / px + 0.5)
                for (at, r) in moonDiscs { line *= clamp(((q - at).length - r - gap) / px + 0.5) }
                if !near { line *= clamp((fromCentre - radius - gap) / px + 0.5) }
                if near { planet *= clamp((d - w - gap) / px + 0.5) }
                lines = max(lines, line * (dark ? 0.75 : 1) * (1 - Float(i) * 0.09))
            }
            colour = mix(colour, fill(q, centre, radius), planet)
            colour = mix(colour, ink, lines)
            for (at, r) in moonDiscs { colour = mix(colour, fill(q, at, r), coverage(q, at, r, px)) }
            return colour
        }
        if dark {
            let field = scatter(Int(1500 * c.aspect / 1.78), seed: 61, aspect: c.aspect, brightest: 0.7)
            draw(field, on: c) { q in smoothstep(radius + 0.02, radius + 0.06, (q - centre).length) }
        }
    }
}

/// Morning on the day side of a teal planet, and its moon's orbit arcing
/// across a light sky.
func daybreakScene(_ c: Canvas) {
    let px = c.pixel, seas = Noise(71), clouds = Noise(72)
    let centre = p(-0.1, 2.08), radius: Float = 1.76
    let light = V(x: 0.45, y: -0.75, z: 0.5).unit
    let orbit = Orbit(p(0.1, 0.55), 1.5)
    let moonAt = orbit.at(-60), moonR: Float = 0.032
    let ocean = Ramp([(0, "#14958f"), (0.5, "#2fb7b0"), (1, "#7fe3d8")])
    let w: Float = 0.0012, gap: Float = 0.0065, ink = hex("#0a95a0")
    c.shade { q, _ in
        var colour = mix(hex("#c9ebea"), hex("#f7fdfc"), smoothstep(-0.5, 0.32, q.y))
        colour = mix(colour, C(1), 0.5 * exp(-(q - p(0.75, -0.45)).length / 0.35))
        let d = q - centre, dist = d.length
        colour = mix(colour, C(1), 0.8 * exp(-max(dist - radius, 0) / 0.03))
        let (line, near) = orbit.distance(q)
        let ring = clamp((w - line) / px + 0.5) * clamp(((q - moonAt).length - moonR - gap) / px + 0.5) * 0.55
        if !near { colour = mix(colour, ink, ring * clamp((dist - radius - gap) / px + 0.5)) }
        var cov = coverage(q, centre, radius, px)
        if near { cov *= clamp((line - w - gap) / px + 0.5) }
        if cov > 0 {
            let rr = min(dist / radius, 1)
            let n = V(x: d.x / radius, y: d.y / radius, z: (1 - rr * rr).squareRoot())
            // Across the surface and down from the limb, foreshortened toward it.
            let around = atan2(d.x, -d.y) * radius, down = pow(max(radius - dist, 0), 0.6)
            let sea = ocean.at(clamp(seas.fbm(around * 2.2, down * 9, 6) * 1.2 + 0.5))
            let cloud = smoothstep(0.0, 0.4, clouds.fbm(around * 2.6, down * 14 + 4, 6))
            var body = mix(sea, C(1), cloud * 0.85) * (0.75 + 0.3 * max(n.dot(light), 0))
            body = mix(body, mix(aqua, C(1), 0.6), 0.85 * pow(1 - n.z, 4))
            colour = mix(colour, body, cov)
        }
        if near { colour = mix(colour, ink, ring) }
        let md = q - moonAt
        let mr = min(md.length / moonR, 1)
        let mn = V(x: md.x / moonR, y: md.y / moonR, z: (1 - mr * mr).squareRoot())
        let moon = mix(hex("#7fcfc6"), C(1), smoothstep(-0.2, 0.5, mn.dot(light)))
        colour = mix(colour, moon, coverage(q, moonAt, moonR, px))
        return colour
    }
}

let scenes: [(String, Scene)] = [
    ("planet", planetScene),
    ("nebula", nebulaScene),
    ("horizon", horizonScene),
    ("eclipse", eclipseScene),
    ("comet", cometScene),
    ("orbits", orbitsScene(dark: true)),
    ("orbits-light", orbitsScene(dark: false)),
    ("daybreak", daybreakScene),
]

// MARK: - Output

/// Light past white bleeds into the other channels and rolls off rather
/// than clipping, so the brightest light goes white, not flat.
func finish(_ c: C) -> C {
    let peak = max(c.r, c.g, c.b)
    let spill = max(peak - 0.85, 0) * 0.4
    func roll(_ x: Float) -> Float { x < 0.8 ? x : 0.8 + 0.2 * (1 - exp(-(x - 0.8) / 0.2)) }
    return C(roll(c.r + spill), roll(c.g + spill), roll(c.b + spill))
}

let srgb = CGColorSpace(name: CGColorSpace.sRGB)!

/// The canvas as an 8-bit sRGB image, dithered so dark gradients don't band.
func image(_ c: Canvas) -> CGImage {
    var bytes = [UInt8](repeating: 255, count: c.w * c.h * 4)
    var rng = RNG(99)
    for i in 0..<(c.w * c.h) {
        let f = finish(c.px[i])
        for (k, v) in [f.r, f.g, f.b].enumerated() {
            let noise = rng.float() - rng.float()
            bytes[i * 4 + k] = UInt8(clamp(encoded(max(v, 0)) * 255 + 0.5 + noise, 0, 255))
        }
    }
    return CGImage(width: c.w, height: c.h, bitsPerComponent: 8, bitsPerPixel: 32, bytesPerRow: c.w * 4, space: srgb,
                   bitmapInfo: CGBitmapInfo(rawValue: CGImageAlphaInfo.noneSkipLast.rawValue),
                   provider: CGDataProvider(data: Data(bytes) as CFData)!, decode: nil, shouldInterpolate: true, intent: .defaultIntent)!
}

func resized(_ image: CGImage, _ w: Int, _ h: Int) -> CGImage {
    let context = CGContext(data: nil, width: w, height: h, bitsPerComponent: 8, bytesPerRow: 0, space: srgb,
                            bitmapInfo: CGImageAlphaInfo.noneSkipLast.rawValue)!
    context.interpolationQuality = .high
    context.draw(image, in: CGRect(x: 0, y: 0, width: w, height: h))
    return context.makeImage()!
}

func save(_ image: CGImage, _ url: URL, quality: Double) {
    let type = url.pathExtension == "png" ? UTType.png : UTType.jpeg
    guard let out = CGImageDestinationCreateWithURL(url as CFURL, type.identifier as CFString, 1, nil) else {
        fatalError("Can't write \(url.path)")
    }
    CGImageDestinationAddImage(out, image, [kCGImageDestinationLossyCompressionQuality: quality] as CFDictionary)
    guard CGImageDestinationFinalize(out) else { fatalError("Couldn't write \(url.path)") }
}

let args = CommandLine.arguments
guard args.count >= 3, ["write", "preview"].contains(args[1]) else {
    print("usage: wallpapers write|preview <folder> [scene…]   scenes: \(scenes.map(\.0).joined(separator: " "))")
    exit(2)
}
let folder = URL(fileURLWithPath: args[2], isDirectory: true)
try FileManager.default.createDirectory(at: folder, withIntermediateDirectories: true)
let wanted = Set(args.dropFirst(3))
if let unknown = wanted.first(where: { name in !scenes.contains { $0.0 == name } }) {
    print("no scene called \(unknown)")
    exit(2)
}
for (name, scene) in scenes where wanted.isEmpty || wanted.contains(name) {
    let preview = args[1] == "preview"
    let canvas = preview ? Canvas(1600, 900) : Canvas(3840, 2160)
    scene(canvas)
    let picture = image(canvas)
    if preview {
        save(picture, folder.appendingPathComponent("\(name).png"), quality: 1)
    } else {
        save(picture, folder.appendingPathComponent("\(name).jpg"), quality: 0.8)
        save(resized(picture, 480, 270), folder.appendingPathComponent("\(name)-thumb.jpg"), quality: 0.8)
    }
    print(name)
}
