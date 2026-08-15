export type SessionState = {
  turn: number;
  lastAutomaticTurn?: number;
  automaticCount: number;
  casualStreak: number;
  lastUserText?: string;
  policy?: string;
};

export type Decision = { allowed: boolean; kind: "explicit" | "automatic" | "none"; reason: string };

const EXPLICIT = ["发张图", "发图片", "生成图片", "自拍", "照片", "表情包", "gif", "show me"];
const BLOCKED = ["报错", "调试", "代码", "考试", "学习", "隐私", "密码", "严肃", "debug", "error", "project", "deploy", "task"];
const PLAYFUL = ["哈哈", "开心", "好耶", "可爱", "调皮", "惊喜", "嘿嘿", "funny", "cute", "yay", "lol"];
const AFFECTIONATE = ["抱抱", "拥抱", "亲亲", "飞吻", "贴贴", "蹭蹭", "哈气", "摸摸头", "牵手"];

function stableSample(seed: string): number {
  let hash = 2166136261;
  for (const char of seed) { hash ^= char.charCodeAt(0); hash = Math.imul(hash, 16777619); }
  return (hash >>> 0) / 2 ** 32;
}

export function decide(message: string, state: SessionState, options: {
  probability: number; playfulProbability: number; forceAfterCasualTurns: number;
  cooldownTurns: number; maxPerSession: number; sessionKey: string;
}): Decision {
  const text = message.toLocaleLowerCase();
  if (EXPLICIT.some((term) => text.includes(term))) return { allowed: true, kind: "explicit", reason: "user_requested" };
  if (BLOCKED.some((term) => text.includes(term))) return { allowed: false, kind: "none", reason: "sensitive_context" };
  if (state.automaticCount >= options.maxPerSession) return { allowed: false, kind: "none", reason: "session_limit" };
  if (state.lastAutomaticTurn !== undefined && state.turn - state.lastAutomaticTurn < options.cooldownTurns) return { allowed: false, kind: "none", reason: "cooldown" };
  if (AFFECTIONATE.some((term) => text.includes(term))) return { allowed: true, kind: "automatic", reason: "affectionate_action" };
  if (state.casualStreak + 1 >= options.forceAfterCasualTurns) return { allowed: true, kind: "automatic", reason: "casual_guarantee" };
  const playful = PLAYFUL.some((term) => text.includes(term));
  if (stableSample(`${options.sessionKey}:${state.turn}:${text}`) >= (playful ? options.playfulProbability : options.probability)) return { allowed: false, kind: "none", reason: "probability_gate" };
  return { allowed: true, kind: "automatic", reason: playful ? "playful_moment" : "casual_moment" };
}
