/**
 * 提供商相关的工具函数
 */

// cdn.jsdelivr.net 在国内经常被连接重置（ERR_CONNECTION_RESET），
// 统一改用同路径语义的 gcore 镜像（/npm/ 与 /gh/ 路径均兼容）
/**
 * 获取提供商类型对应的图标
 * @param {string} type - 提供商类型
 * @returns {string} 图标 URL
 */
export function getProviderIcon(type) {
  const icons = {
    'openai': 'https://gcore.jsdelivr.net/npm/@lobehub/icons-static-svg@latest/icons/openai.svg',
    'azure': 'https://gcore.jsdelivr.net/npm/@lobehub/icons-static-svg@latest/icons/azure.svg',
    'xai': 'https://gcore.jsdelivr.net/npm/@lobehub/icons-static-svg@latest/icons/xai.svg',
    'anthropic': 'https://gcore.jsdelivr.net/npm/@lobehub/icons-static-svg@latest/icons/anthropic.svg',
    'ollama': 'https://gcore.jsdelivr.net/npm/@lobehub/icons-static-svg@latest/icons/ollama.svg',
    'google': 'https://gcore.jsdelivr.net/npm/@lobehub/icons-static-svg@latest/icons/gemini-color.svg',
    'deepseek': 'https://gcore.jsdelivr.net/npm/@lobehub/icons-static-svg@latest/icons/deepseek.svg',
    'modelscope': 'https://gcore.jsdelivr.net/npm/@lobehub/icons-static-svg@latest/icons/modelscope.svg',
    'zhipu': 'https://gcore.jsdelivr.net/npm/@lobehub/icons-static-svg@latest/icons/zhipu.svg',
    'nvidia': 'https://gcore.jsdelivr.net/npm/@lobehub/icons-static-svg@latest/icons/nvidia-color.svg',
    'siliconflow': 'https://gcore.jsdelivr.net/npm/@lobehub/icons-static-svg@latest/icons/siliconcloud.svg',
    'moonshot': 'https://gcore.jsdelivr.net/npm/@lobehub/icons-static-svg@latest/icons/kimi.svg',
    'kimi': 'https://gcore.jsdelivr.net/npm/@lobehub/icons-static-svg@latest/icons/kimi.svg',
    'kimi-code': 'https://gcore.jsdelivr.net/npm/@lobehub/icons-static-svg@latest/icons/kimi.svg',
    'longcat': 'https://gcore.jsdelivr.net/npm/@lobehub/icons-static-svg@latest/icons/longcat-color.svg',
    'ppio': 'https://gcore.jsdelivr.net/npm/@lobehub/icons-static-svg@latest/icons/ppio.svg',
    'dify': 'https://gcore.jsdelivr.net/npm/@lobehub/icons-static-svg@latest/icons/dify-color.svg',
    "coze": "https://gcore.jsdelivr.net/npm/@lobehub/icons-static-svg@1.66.0/icons/coze.svg",
    'dashscope': 'https://gcore.jsdelivr.net/npm/@lobehub/icons-static-svg@latest/icons/alibabacloud-color.svg',
    'deerflow': 'https://gcore.jsdelivr.net/gh/bytedance/deer-flow@main/frontend/public/images/deer.svg',
    'fastgpt': 'https://gcore.jsdelivr.net/npm/@lobehub/icons-static-svg@latest/icons/fastgpt-color.svg',
    'lm_studio': 'https://gcore.jsdelivr.net/npm/@lobehub/icons-static-svg@latest/icons/lmstudio.svg',
    'fishaudio': 'https://gcore.jsdelivr.net/npm/@lobehub/icons-static-svg@latest/icons/fishaudio.svg',
    'minimax': 'https://gcore.jsdelivr.net/npm/@lobehub/icons-static-svg@latest/icons/minimax.svg',
    'minimax-token-plan': 'https://gcore.jsdelivr.net/npm/@lobehub/icons-static-svg@latest/icons/minimax.svg',
    'mimo': 'https://gcore.jsdelivr.net/npm/simple-icons@latest/icons/xiaomi.svg',
    'xiaomi': 'https://gcore.jsdelivr.net/npm/simple-icons@latest/icons/xiaomi.svg',
    'xiaomi-token-plan': 'https://gcore.jsdelivr.net/npm/simple-icons@latest/icons/xiaomi.svg',
    '302ai': 'https://gcore.jsdelivr.net/npm/@lobehub/icons-static-svg@1.53.0/icons/ai302-color.svg',
    'microsoft': 'https://gcore.jsdelivr.net/npm/@lobehub/icons-static-svg@latest/icons/microsoft.svg',
    'vllm': 'https://gcore.jsdelivr.net/npm/@lobehub/icons-static-svg@latest/icons/vllm.svg',
    'groq': 'https://gcore.jsdelivr.net/npm/@lobehub/icons-static-svg@latest/icons/groq.svg',
    'aihubmix': 'https://gcore.jsdelivr.net/npm/@lobehub/icons-static-svg@latest/icons/aihubmix-color.svg',
    'openrouter': 'https://gcore.jsdelivr.net/npm/@lobehub/icons-static-svg@latest/icons/openrouter.svg',
    "tokenpony": "https://tokenpony.cn/tokenpony-web/logo.png",
    "compshare": "https://compshare.cn/favicon.ico",
    "xinference": "https://gcore.jsdelivr.net/npm/@lobehub/icons-static-svg@latest/icons/xinference-color.svg",
    "bailian": "https://gcore.jsdelivr.net/npm/@lobehub/icons-static-svg@latest/icons/bailian-color.svg",
    "volcengine": 'https://gcore.jsdelivr.net/npm/@lobehub/icons-static-svg@latest/icons/volcengine-color.svg',
    'huggingface': 'https://gcore.jsdelivr.net/npm/@lobehub/icons-static-svg@latest/icons/huggingface.svg',
  };
  return icons[type] || '';
}

/**
 * 获取提供商简介
 * @param {Object} template - 模板对象
 * @param {string} name - 提供商名称
 * @param {Function} tm - 翻译函数
 * @returns {string} 提供商描述
 */
export function getProviderDescription(template, name, tm) {
  if (name === 'OpenAI') {
    return tm('providers.description.openai', { type: template.type });
  } else if (template.provider === 'kimi-code') {
    return tm('providers.description.kimi_code');
  } else if (name === 'vLLM Rerank') {
    return tm('providers.description.vllm_rerank', { type: template.type });
  }
  return tm('providers.description.default', { type: template.type });
}
