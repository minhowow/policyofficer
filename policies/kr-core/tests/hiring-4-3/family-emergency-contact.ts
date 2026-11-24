// 함정 — 비상연락망이다. 학력·직업·재산을 받지 않는다.
export interface EmergencyContact {
  relation: "부모" | "형제" | "배우자";
  phone: string;
}
