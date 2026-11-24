// 가족 동반 해외 주재원. 동반 가족의 재직 여부가 비자 요건이라 그 공고에서만 받는다.
import { z } from "zod";

export const applicantSchema = (jobRequiresFamilyVisa: boolean) =>
  z.object({
    name: z.string(),
    parentJob: jobRequiresFamilyVisa ? z.string() : z.undefined(),
  });
