import { createTheme, type CSSVariablesResolver, type MantineColorsTuple } from "@mantine/core";

const tgBlue: MantineColorsTuple = [
  "#e3f0ff",
  "#b8d9ff",
  "#8bc0ff",
  "#5ea7ff",
  "#2990ff",
  "#2481cc",
  "#1d73b8",
  "#1661a0",
  "#0f4f88",
  "#083d70",
];

export const mantineTheme = createTheme({
  primaryColor: "tgBlue",
  primaryShade: { light: 5, dark: 4 },
  colors: { tgBlue },
  fontFamily:
    'system-ui, -apple-system, BlinkMacSystemFont, "Roboto", "Helvetica Neue", sans-serif',
  defaultRadius: 10,
  cursorType: "pointer",
  components: {
    Button: { defaultProps: { radius: 10 } },
    TextInput: { defaultProps: { radius: 10 } },
    Textarea: { defaultProps: { radius: 10 } },
    FileInput: { defaultProps: { radius: 10 } },
    SegmentedControl: { defaultProps: { radius: 10 } },
    Drawer: {
      defaultProps: {
        radius: "lg",
        position: "bottom",
        overlayProps: { blur: 2 },
      },
      styles: {
        content: { background: "var(--tg-theme-section-bg-color)" },
        header: { background: "var(--tg-theme-section-bg-color)" },
      },
    },
  },
});

export const tgPalette = {
  light: {
    "--tg-theme-bg-color": "#efeff4",
    "--tg-theme-section-bg-color": "#ffffff",
    "--tg-theme-secondary-bg-color": "#efeff4",
    "--tg-theme-text-color": "#000000",
    "--tg-theme-hint-color": "#999999",
    "--tg-theme-link-color": "#2481cc",
    "--tg-theme-button-color": "#2481cc",
    "--tg-theme-button-text-color": "#ffffff",
    "--tg-theme-destructive-text-color": "#e53935",
  },
  dark: {
    "--tg-theme-bg-color": "#17181c",
    "--tg-theme-section-bg-color": "#202127",
    "--tg-theme-secondary-bg-color": "#202127",
    "--tg-theme-text-color": "#ffffff",
    "--tg-theme-hint-color": "#aaaaaa",
    "--tg-theme-link-color": "#2990ff",
    "--tg-theme-button-color": "#2990ff",
    "--tg-theme-button-text-color": "#ffffff",
    "--tg-theme-destructive-text-color": "#ec3942",
  },
} as const;

export const cssVariablesResolver: CSSVariablesResolver = () => ({
  variables: {},
  light: { ...tgPalette.light },
  dark: { ...tgPalette.dark },
});
