// "Bottle glass" brand colors - amberglass/oliveglass/brickglass are custom
// Tailwind v4 scales defined in app/assets/css/main.css's @theme block (see
// @nuxt/ui's colors plugin, which resolves each of these names to
// --color-<name>-<shade> custom properties rather than a built-in Tailwind
// color).
export default defineAppConfig({
  ui: {
    colors: {
      primary: 'amberglass',
      secondary: 'oliveglass',
      success: 'oliveglass',
      info: 'cyan',
      warning: 'amberglass',
      error: 'brickglass',
      neutral: 'slate',
    },
  },
})
