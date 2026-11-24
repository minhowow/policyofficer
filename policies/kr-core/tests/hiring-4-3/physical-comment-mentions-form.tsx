// 건강검진 결과 화면이다. 지원서 폼과 생김새가 비슷해 같은 틀을 쓴다.
export function CheckupResult({ result }: { result: { height: number; weight: number } }) {
  return (
    <dl>
      <dt>키</dt>
      <dd>{result.height} cm</dd>
      <dt>체중</dt>
      <dd>{result.weight} kg</dd>
    </dl>
  );
}
