import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { insightsApi } from "@/features/ai-assistant/api/insights-api";
import type {
  AiReportTypeValue,
  FeedbackRatingValue,
  GenerateAiReportInput,
  GenerateRecommendationInput,
} from "@/features/ai-assistant/types";

export function useRecommendations(organizationId: string | null, conversationId?: string) {
  return useQuery({
    queryKey: ["ai-assistant", "recommendations", organizationId, conversationId],
    queryFn: () => insightsApi.listRecommendations(organizationId as string, conversationId),
    enabled: organizationId !== null,
    staleTime: 15_000,
  });
}

export function useGenerateRecommendation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: GenerateRecommendationInput) => insightsApi.generateRecommendation(input),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["ai-assistant", "recommendations"] });
    },
  });
}

export function useDecideRecommendation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ recommendationId, accept }: { recommendationId: string; accept: boolean }) =>
      insightsApi.decideRecommendation(recommendationId, accept),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["ai-assistant", "recommendations"] });
    },
  });
}

export function useAiReports(organizationId: string | null, reportType?: AiReportTypeValue) {
  return useQuery({
    queryKey: ["ai-assistant", "reports", organizationId, reportType],
    queryFn: () => insightsApi.listReports(organizationId as string, reportType),
    enabled: organizationId !== null,
    staleTime: 15_000,
  });
}

export function useGenerateAiReport() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: GenerateAiReportInput) => insightsApi.generateReport(input),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["ai-assistant", "reports"] });
    },
  });
}

export function useSubmitFeedback() {
  return useMutation({
    mutationFn: ({
      organizationId,
      messageId,
      rating,
      comment,
    }: {
      organizationId: string;
      messageId: string;
      rating: FeedbackRatingValue;
      comment?: string;
    }) => insightsApi.submitFeedback(organizationId, messageId, rating, comment),
  });
}

export function useMemoryEntries(organizationId: string | null) {
  return useQuery({
    queryKey: ["ai-assistant", "memory", organizationId],
    queryFn: () => insightsApi.listMemory(organizationId as string),
    enabled: organizationId !== null,
    staleTime: 30_000,
  });
}

export function useAiStatistics(organizationId: string | null) {
  return useQuery({
    queryKey: ["ai-assistant", "statistics", organizationId],
    queryFn: () => insightsApi.statistics(organizationId as string, false),
    enabled: organizationId !== null,
    staleTime: 60_000,
  });
}

export function useRecomputeAiStatistics() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (organizationId: string) => insightsApi.statistics(organizationId, true),
    onSuccess: (data, organizationId) => {
      queryClient.setQueryData(["ai-assistant", "statistics", organizationId], data);
    },
  });
}
