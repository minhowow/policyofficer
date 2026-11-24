// 이름만 직무 요건처럼 보인다. 플래그를 읽을 뿐 신체 조건 칸을 가리지 않는다.
const jobRequiresDriverLicense = true;

export function ApplicationForm() {
  return (
    <form action="/apply/submit" method="post">
      <input name="license" placeholder="운전면허" disabled={!jobRequiresDriverLicense} />
      <input name="height" type="number" placeholder="키(cm)" />
      <input name="weight" type="number" placeholder="체중(kg)" />
    </form>
  );
}
