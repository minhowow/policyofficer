// 소방관 채용. 체력 기준이 직무 요건이라 해당 공고에서만 신체 조건을 받는다.
export function ApplicationForm({ jobRequiresPhysicalTest }: { jobRequiresPhysicalTest: boolean }) {
  return (
    <form action="/apply/submit" method="post">
      <input name="name" placeholder="이름" />
      {jobRequiresPhysicalTest && <input name="height" type="number" placeholder="키(cm)" />}
      {jobRequiresPhysicalTest && <input name="weight" type="number" placeholder="체중(kg)" />}
      <button type="submit">지원하기</button>
    </form>
  );
}
