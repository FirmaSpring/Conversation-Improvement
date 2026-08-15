export type SessionState = {
  turn: number;
  lastAutomaticTurn?: number;
  automaticCount: number;
  casualStreak: number;
};

export type Decision = { allowed: boolean; kind: "explicit" | "automatic" | "none"; reason: string };

const EXPLICIT = ["发张图", "发图片", "生成图片", "生成一张", "画一张", "看看你", "看你", "自拍", "照片", "表情包", "gif", "image", "picture", "show me"];
const SENSITIVE = ["报错", "错误", "调试", "代码", "考试", "作业", "学习", "难受", "痛苦", "生病", "隐私", "密码", "事故", "去世", "分手", "严肃", "debug", "error", "项目", "重构", "部署", "测试", "终端", "命令", "算法", "论文", "报告", "分析", "任务", "project", "refactor", "deploy", "terminal", "command", "algorithm", "report", "analysis", "task"];
const PLAYFUL = ["哈哈", "开心", "好耶", "可爱", "调皮", "惊喜", "逗", "笑死", "庆祝", "嘿嘿", "有意思", "funny", "cute", "yay", "lol"];
const AFFECTIONATE = ["抱抱", "拥抱", "抱一下", "亲亲", "亲一口", "飞吻", "贴贴", "蹭蹭", "哈气", "呵气", "暖暖", "摸摸头", "摸头", "牵手", "拉手"];

function stableSample(seed: string): number {
  let hash = 2166136261;
  for (const char of seed) { hash ^= char.charCodeAt(0); hash = Math.imul(hash, 16777619); }
  return (hash >>> 0) / 2 ** 32;
}

export function decide(message: string, state: SessionState, sessionKey: string, options = {
  probability: 0.32, playfulProbability: 0.65, forceAfterCasualTurns: 4, cooldownTurns: 5, maxPerSession: 20,
}): Decision {
  const text = message.toLocaleLowerCase();
  if (EXPLICIT.some((term) => text.includes(term))) return { allowed: true, kind: "explicit", reason: "user_requested" };
  if (SENSITIVE.some((term) => text.includes(term))) return { allowed: false, kind: "none", reason: "sensitive_context" };
  if (state.automaticCount >= options.maxPerSession) return { allowed: false, kind: "none", reason: "session_limit" };
  if (state.lastAutomaticTurn !== undefined && state.turn - state.lastAutomaticTurn < options.cooldownTurns) return { allowed: false, kind: "none", reason: "cooldown" };
  if (AFFECTIONATE.some((term) => text.includes(term))) return { allowed: true, kind: "automatic", reason: "affectionate_action" };
  if (state.casualStreak + 1 >= options.forceAfterCasualTurns) return { allowed: true, kind: "automatic", reason: "casual_guarantee" };
  const playful = PLAYFUL.some((term) => text.includes(term));
  const threshold = playful ? options.playfulProbability : options.probability;
  if (stableSample(`${sessionKey}:${state.turn}:${text}`) >= threshold) return { allowed: false, kind: "none", reason: "probability_gate" };
  return { allowed: true, kind: "automatic", reason: playful ? "playful_moment" : "casual_moment" };
}
