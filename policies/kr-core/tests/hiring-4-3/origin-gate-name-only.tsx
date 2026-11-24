// 블라인드 채용이라는 이름만 있고, 출신지역·혼인여부 칸은 그대로 받는다.
const blindHiringEnabled = false;

export function JobApplicationForm() {
  return (
    <form action="/recruit/apply" method="post">
      <input name="name" placeholder={blindHiringEnabled ? "지원자 번호" : "이름"} />
      <input name="hometown" placeholder="출신지역" />
      <input name="maritalStatus" placeholder="혼인여부" />
    </form>
  );
}
