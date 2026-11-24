// 입사지원 폼. 출신지역과 혼인여부를 모든 지원자에게 받는다.
export function JobApplicationForm() {
  return (
    <form action="/recruit/apply" method="post">
      <input name="name" placeholder="이름" />
      <input name="hometown" placeholder="출신지역" />
      <select name="maritalStatus">
        <option value="single">미혼</option>
        <option value="married">기혼</option>
      </select>
    </form>
  );
}
