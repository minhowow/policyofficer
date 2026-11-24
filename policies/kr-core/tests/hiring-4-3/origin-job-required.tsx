// 재외공관 파견직. 거주지 요건이 직무 요건이라 해당 공고에서만 받는다.
export function JobApplicationForm({ jobRequiresResidency }: { jobRequiresResidency: boolean }) {
  return (
    <form action="/recruit/apply" method="post">
      <input name="name" placeholder="이름" />
      {jobRequiresResidency && <input name="hometown" placeholder="거주 지역" />}
    </form>
  );
}
