// 직무 필요라는 이름만 두고 가족 항목은 모든 지원자에게 받는다.
import { z } from "zod";

const jobRequiresBackgroundCheck = true;

export const applicantSchema = z.object({
  name: z.string(),
  backgroundCheck: z.boolean().default(jobRequiresBackgroundCheck),
  parentJob: z.string(),
  familyEducation: z.string(),
});
