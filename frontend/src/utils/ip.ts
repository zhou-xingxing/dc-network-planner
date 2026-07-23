export function getIpVersion(ip: string): 4 | 6 | null {
  if (isValidIpv4(ip)) return 4
  if (expandIpv6(ip)) return 6
  return null
}

export function recommendedGatewayIp(cidr: string, isPrivate: boolean): string {
  const [ip, prefixText] = cidr.trim().split('/')
  const prefix = Number(prefixText)
  const ipVersion = getIpVersion(ip)
  const maxPrefix = ipVersion === 4 ? 32 : 128
  if (!ipVersion || !Number.isInteger(prefix) || prefix < 0 || prefix > maxPrefix) return ''
  if (ipVersion === 6) return recommendedIpv6GatewayIp(ip, prefix)

  const base = ipv4ToNumber(ip)
  const mask = prefix === 0 ? 0 : (0xffffffff << (32 - prefix)) >>> 0
  const network = base & mask
  const broadcast = (network | (~mask >>> 0)) >>> 0
  if (network === broadcast) return numberToIpv4(network)
  if (isPrivate) return numberToIpv4(prefix < 31 ? network + 1 : network)
  return numberToIpv4(prefix < 31 ? broadcast - 1 : broadcast)
}

function isValidIpv4(ip: string): boolean {
  const parts = ip.split('.')
  return parts.length === 4 && parts.every(part => {
    if (!/^\d+$/.test(part)) return false
    if (part.length > 1 && part.startsWith('0')) return false
    const value = Number(part)
    return value >= 0 && value <= 255
  })
}

function expandIpv6(ip: string): number[] | null {
  if (!ip.includes(':') || ip.includes(':::') || ip.indexOf('::') !== ip.lastIndexOf('::')) return null
  const hasCompression = ip.includes('::')
  const [head = '', tail = ''] = hasCompression ? ip.split('::') : [ip, '']
  const headSegments = parseIpv6Section(head)
  const tailSegments = parseIpv6Section(tail)
  if (!headSegments || !tailSegments) return null
  if (head.includes('.') && hasCompression) return null

  const segmentCount = headSegments.length + tailSegments.length
  if (!hasCompression) return segmentCount === 8 ? headSegments : null
  if (segmentCount >= 8) return null
  return [...headSegments, ...Array<number>(8 - segmentCount).fill(0), ...tailSegments]
}

function parseIpv6Section(section: string): number[] | null {
  if (!section) return []
  const parts = section.split(':')
  if (parts.some(part => !part)) return null
  const segments: number[] = []
  for (const [index, part] of parts.entries()) {
    if (part.includes('.')) {
      if (index !== parts.length - 1 || !isValidIpv4(part)) return null
      const bytes = part.split('.').map(Number)
      segments.push((bytes[0] << 8) | bytes[1], (bytes[2] << 8) | bytes[3])
      continue
    }
    if (!/^[\da-fA-F]{1,4}$/.test(part)) return null
    segments.push(Number.parseInt(part, 16))
  }
  return segments
}

function recommendedIpv6GatewayIp(ip: string, prefix: number): string {
  const segments = expandIpv6(ip)
  if (!segments) return ''
  const address = segments.reduce((value, segment) => (value << 16n) | BigInt(segment), 0n)
  const hostBits = 128 - prefix
  const network = hostBits === 128 ? 0n : (address >> BigInt(hostBits)) << BigInt(hostBits)
  const gateway = prefix < 127 ? network + 1n : network
  return bigIntToIpv6(gateway)
}

function bigIntToIpv6(value: bigint): string {
  const segments = Array.from({ length: 8 }, (_, index) =>
    Number((value >> BigInt((7 - index) * 16)) & 0xffffn)
  )
  let bestStart = -1
  let bestLength = 0
  for (let index = 0; index < segments.length;) {
    if (segments[index] !== 0) {
      index += 1
      continue
    }
    let end = index
    while (end < segments.length && segments[end] === 0) end += 1
    if (end - index > bestLength) {
      bestStart = index
      bestLength = end - index
    }
    index = end
  }
  const hex = segments.map(segment => segment.toString(16))
  if (bestLength < 2) return hex.join(':')
  const before = hex.slice(0, bestStart).join(':')
  const after = hex.slice(bestStart + bestLength).join(':')
  return `${before}::${after}`
}

function ipv4ToNumber(ip: string): number {
  return ip.split('.').reduce((acc: number, part: string) => ((acc << 8) + Number(part)) >>> 0, 0)
}

function numberToIpv4(value: number): string {
  return [24, 16, 8, 0].map((shift: number) => (value >>> shift) & 255).join('.')
}
