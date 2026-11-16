// Palette from the Career Buddy mockups. Each entry: [light, dark].
// Exposed as semantic color tokens under the `app.` namespace (e.g. bg="app.surface").
// Entries with the same value in both modes are intentional (no dark variant in the mockup).
export const palette = {
  bg: ['#FFF8EE', '#1E1A33'],
  surface: ['#FFFFFF', '#2A2445'],
  surface2: ['#FFF3E0', '#241F3D'],
  border: ['#F2D7B6', '#433A66'],
  borderStrong: ['#E9C49A', '#5A4E85'],
  dash: ['#F6AD55', '#8B7FBF'],
  text: ['#2D2250', '#F7F3FF'],
  text2: ['#3D3266', '#E9E2FF'],
  text3: ['#55487A', '#CFC5F0'],
  muted: ['#6E6490', '#B3A8DA'],
  hover: ['#FDEBD3', '#352D57'],
  primary: ['#6B46C1', '#9F7AEA'],
  onPrimary: ['#FFFFFF', '#1E1A33'],
  link: ['#6B46C1', '#C4B1FF'],
  activeBg: ['#FFE4D1', '#4D3340'],
  activeText: ['#9C3B12', '#FFC9A8'],
  infoTag: ['#DCD0FF', '#4C3D8A'],
  okBg: ['#C6F6D5', '#1F4D3A'],
  okText: ['#22543D', '#B7F5D2'],
  warnBg: ['#FFF0B3', '#5A4A10'],
  warnText: ['#7A4B00', '#FFF0B3'],
  warnPanel: ['#FFF9DB', '#3D3418'],
  warnBorder: ['#FFE066', '#6B5A1A'],
  missBg: ['#FFD6E0', '#5C2140'],
  missText: ['#9B1C4F', '#FFD6E0'],
  done: ['#2FB67C', '#2FB67C'],
  scrim: ['rgba(45,34,80,0.55)', 'rgba(0,0,0,0.6)'],
  nodeFill: ['#EDE7FF', '#3A2F63'],
  nodeText: ['#4C2F9E', '#E2D9FF'],
  nodeStroke: ['#8B6CE0', '#A58BFF'],
} as const satisfies Record<string, readonly [string, string]>

export type PaletteKey = keyof typeof palette
