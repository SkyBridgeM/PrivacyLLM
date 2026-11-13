export const labels = {
  PERSON: "人名",
  ORGANIZATION: "机构",
  PROJECT: "项目",
  DEPARTMENT: "部门",
  LOCATION: "详细地址",
  PHONE: "手机号",
  ID_CARD: "身份证",
  BANK_CARD: "银行卡",
  EMAIL: "邮箱",
  CREDIT_CODE: "信用代码",
  SECURITY_CODE: "证券代码",
  AMOUNT: "金额",
  DATE: "日期",
  IP_ADDRESS: "IP 地址",
  BUSINESS_SECRET: "业务秘密",
  CUSTOM: "自定义",
} as const;
export type EntityType = keyof typeof labels;
export interface Entity {
  id: string;
  text: string;
  entity_type: EntityType;
  start: number;
  end: number;
  confidence: number;
  source: string;
  selected: boolean;
  replacement: string | null;
  reason: string | null;
  conflict: boolean;
}
export interface Mapping {
  version: number;
  created_at: string;
  document_id: string;
  mappings: {
    placeholder: string;
    original: string;
    entity_type: EntityType;
  }[];
}
export interface DictionaryEntry {
  value: string;
  entity_type: EntityType;
  enabled: boolean;
  selected: boolean;
}
export interface CustomRule {
  name: string;
  pattern: string;
  entity_type: EntityType;
  enabled: boolean;
  selected: boolean;
  test_samples: string[];
}
export interface Settings {
  entity_defaults: Record<EntityType, boolean>;
}
export interface ModelStatus {
  available: boolean;
  installed: boolean;
  engine_available: boolean;
  loading: boolean;
  model: string;
  message: string;
  download: {
    active: boolean;
    received: number;
    total: number;
    error: string | null;
  };
}
export const cpLength = (text: string) => Array.from(text).length;
export const cpSlice = (text: string, start: number, end?: number) =>
  Array.from(text).slice(start, end).join("");
export const utf16ToCodePoint = (text: string, offset: number) =>
  cpLength(text.slice(0, offset));
export const overlap = (
  a: Pick<Entity, "start" | "end">,
  b: Pick<Entity, "start" | "end">,
) => a.start < b.end && b.start < a.end;
export function sourceLabel(source: string) {
  return source
    .split("+")
    .map((s) =>
      s.startsWith("custom_regex")
        ? "自定义规则"
        : ({
            manual: "手动",
            dictionary: "词典",
            regex: "规则",
            semantic: "语义",
            qwen: "语义",
          }[s] ?? s),
    )
    .join(" / ");
}
