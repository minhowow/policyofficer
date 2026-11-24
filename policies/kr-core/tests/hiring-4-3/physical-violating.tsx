// 입사지원 폼. 모든 지원자에게 키·체중을 받는다.
export function ApplicationForm() {
  return (
    <form action="/apply/submit" method="post">
      <input name="name" placeholder="이름" />
      <input name="height" type="number" placeholder="키(cm)" />
      <input name="weight" type="number" placeholder="체중(kg)" />
      <button type="submit">지원하기</button>
    </form>
  );
}
