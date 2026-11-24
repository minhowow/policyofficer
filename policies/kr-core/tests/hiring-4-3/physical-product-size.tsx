// 함정 — 상품 치수다. 채용과 무관한 화면이다.
export interface ProductSize {
  height: number;
  weight: number;
}

export function sizeLabel(size: ProductSize) {
  return `높이 ${size.height}cm · 무게 ${size.weight}kg`;
}
