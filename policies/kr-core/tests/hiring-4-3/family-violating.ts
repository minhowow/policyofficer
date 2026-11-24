// 지원자 스키마. 부모의 직업과 학력을 받는다.
import { z } from "zod";

export const applicantSchema = z.object({
  name: z.string(),
  parentJob: z.string(),
  parentEducation: z.string(),
  familyAssets: z.number().optional(),
});
