import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { templatesApi } from "@/features/reporting/api/templates-api";
import type {
  CategoryCreateInput,
  ReportCategory,
  TemplateCreateInput,
  TemplateVersionInput,
} from "@/features/reporting/types";

export function useTemplates(organizationId: string | null, category?: ReportCategory) {
  return useQuery({
    queryKey: ["reporting", "templates", organizationId, category],
    queryFn: () => templatesApi.list(organizationId as string, category),
    enabled: organizationId !== null,
    staleTime: 30_000,
  });
}

export function useTemplate(templateId: string | null) {
  return useQuery({
    queryKey: ["reporting", "templates", templateId],
    queryFn: () => templatesApi.getById(templateId as string),
    enabled: templateId !== null,
    staleTime: 15_000,
  });
}

export function useTemplateParameters(templateId: string | null) {
  return useQuery({
    queryKey: ["reporting", "templates", templateId, "parameters"],
    queryFn: () => templatesApi.listParameters(templateId as string),
    enabled: templateId !== null,
    staleTime: 30_000,
  });
}

export function useTemplateVersions(templateId: string | null) {
  return useQuery({
    queryKey: ["reporting", "templates", templateId, "versions"],
    queryFn: () => templatesApi.listVersions(templateId as string),
    enabled: templateId !== null,
    staleTime: 15_000,
  });
}

export function useReportCategories(organizationId: string | null) {
  return useQuery({
    queryKey: ["reporting", "categories", organizationId],
    queryFn: () => templatesApi.listCategories(organizationId as string),
    enabled: organizationId !== null,
    staleTime: 60_000,
  });
}

export function useCreateTemplate() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: TemplateCreateInput) => templatesApi.create(input),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["reporting", "templates"] });
    },
  });
}

export function useAddTemplateVersion(templateId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: TemplateVersionInput) => templatesApi.addVersion(templateId, input),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["reporting", "templates"] });
    },
  });
}

export function useApproveTemplate() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (templateId: string) => templatesApi.approve(templateId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["reporting", "templates"] });
    },
  });
}

export function useArchiveTemplate() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (templateId: string) => templatesApi.archive(templateId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["reporting", "templates"] });
    },
  });
}

export function useCreateCategory() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: CategoryCreateInput) => templatesApi.createCategory(input),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["reporting", "categories"] });
    },
  });
}
