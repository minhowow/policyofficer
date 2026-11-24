// 함정 — 배송지다. 채용과 무관한 화면이다.
export interface ShippingAddress {
  hometown?: string;
  postalCode: string;
}

export function formatAddress(a: ShippingAddress) {
  return `${a.hometown ?? ""} ${a.postalCode}`;
}
