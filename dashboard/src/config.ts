export type ThemeMode = 'light' | 'dark' | 'system';

export type ConfigProps = {
  Sidebar_drawer: boolean;
  Customizer_drawer: boolean;
  mini_sidebar: boolean;
  fontTheme: string;
  uiTheme: string;
  themeMode: ThemeMode;
  inputBg: boolean;
};

function checkThemeMode(): ThemeMode {
  const mode = localStorage.getItem('themeMode') as ThemeMode | null;
  // 暗色已禁用：历史 dark 偏好回退为亮色
  if (mode === 'dark') {
    localStorage.setItem('themeMode', 'light');
    return 'light';
  }
  if (mode === 'light' || mode === 'system') return mode;

  const legacyTheme = localStorage.getItem('uiTheme');
  if (legacyTheme === 'PurpleThemeDark') {
    localStorage.setItem('themeMode', 'light');
    return 'light';
  }
  if (legacyTheme === 'PurpleTheme') {
    localStorage.setItem('themeMode', 'light');
    return 'light';
  }

  localStorage.setItem('themeMode', 'system');
  return 'system';
}

export function resolveUiTheme(mode: ThemeMode): string {
  // 暗色已禁用：任何模式（含 system）都解析为亮色主题
  void mode;
  return 'PurpleTheme';
}

const themeMode = checkThemeMode();
const uiTheme = resolveUiTheme(themeMode);

localStorage.setItem('uiTheme', uiTheme);

const config: ConfigProps = {
  Sidebar_drawer: true,
  Customizer_drawer: false,
  mini_sidebar: false,
  fontTheme: 'Roboto',
  uiTheme,
  themeMode,
  inputBg: false,
};

export default config;
