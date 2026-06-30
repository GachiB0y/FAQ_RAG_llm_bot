import { useEffect, useState } from 'react';
import { useIntl } from 'react-intl';
import {
  Box,
  Button,
  Divider,
  FormControl,
  FormHelperText,
  FormLabel,
  Heading,
  Input,
  NumberDecrementStepper,
  NumberIncrementStepper,
  NumberInput,
  NumberInputField,
  NumberInputStepper,
  Select,
  Skeleton,
  Slider,
  SliderFilledTrack,
  SliderThumb,
  SliderTrack,
  useToast,
  VStack,
} from '@chakra-ui/react';
import type { SystemSettings } from '@entities/settings';
import { useSettings, useUpdateSettings } from '@entities/settings';

interface FormData {
  llm_provider: SystemSettings['llm_provider'];
  embedding_provider: SystemSettings['embedding_provider'];
  embedding_model: string;
  chunk_size: number;
  chunk_overlap: number;
  similarity_threshold: number;
  top_k_results: number;
}

const DEFAULT_FORM_DATA: FormData = {
  llm_provider: 'openai',
  embedding_provider: 'openai',
  embedding_model: '',
  chunk_size: 500,
  chunk_overlap: 50,
  similarity_threshold: 0.7,
  top_k_results: 5,
};

export const SettingsForm = () => {
  const { formatMessage } = useIntl();
  const toast = useToast();
  const { data: settings, isLoading, isError } = useSettings();
  const updateMutation = useUpdateSettings();

  const [formData, setFormData] = useState<FormData>(DEFAULT_FORM_DATA);

  useEffect(() => {
    if (settings) {
      setFormData({
        llm_provider: settings.llm_provider,
        embedding_provider: settings.embedding_provider,
        embedding_model: settings.embedding_model,
        chunk_size: settings.chunk_size,
        chunk_overlap: settings.chunk_overlap,
        similarity_threshold: settings.similarity_threshold,
        top_k_results: settings.top_k_results,
      });
    }
  }, [settings]);

  useEffect(() => {
    if (isError) {
      toast({
        title: formatMessage({ id: 'settings.load.error' }),
        status: 'error',
        duration: 5000,
      });
    }
  }, [isError, formatMessage, toast]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    try {
      await updateMutation.mutateAsync(formData);
      toast({
        title: formatMessage({ id: 'settings.save.success' }),
        status: 'success',
        duration: 3000,
      });
    } catch {
      toast({
        title: formatMessage({ id: 'settings.save.error' }),
        status: 'error',
        duration: 3000,
      });
    }
  };

  if (isLoading) {
    return (
      <VStack spacing={4} align="stretch">
        <Skeleton height="40px" />
        <Skeleton height="40px" />
        <Skeleton height="40px" />
        <Skeleton height="40px" />
        <Skeleton height="40px" />
        <Skeleton height="40px" />
        <Skeleton height="40px" />
      </VStack>
    );
  }

  return (
    <Box as="form" onSubmit={handleSubmit}>
      <VStack spacing={6} align="stretch">
        <Box>
          <Heading size="sm" mb={4}>
            {formatMessage({ id: 'settings.section.rag' })}
          </Heading>
          <VStack spacing={4} align="stretch">
            <FormControl>
              <FormLabel>{formatMessage({ id: 'settings.chunk_size' })}</FormLabel>
              <NumberInput
                aria-label={formatMessage({ id: 'settings.chunk_size' })}
                value={formData.chunk_size}
                onChange={(_, value) => setFormData({ ...formData, chunk_size: value || 100 })}
                min={100}
                max={2000}
                isDisabled={updateMutation.isPending}
              >
                <NumberInputField />
                <NumberInputStepper>
                  <NumberIncrementStepper />
                  <NumberDecrementStepper />
                </NumberInputStepper>
              </NumberInput>
              <FormHelperText>
                {formatMessage({ id: 'settings.chunk_size.help' })}
              </FormHelperText>
            </FormControl>

            <FormControl>
              <FormLabel>{formatMessage({ id: 'settings.chunk_overlap' })}</FormLabel>
              <NumberInput
                aria-label={formatMessage({ id: 'settings.chunk_overlap' })}
                value={formData.chunk_overlap}
                onChange={(_, value) => setFormData({ ...formData, chunk_overlap: value || 0 })}
                min={0}
                max={200}
                isDisabled={updateMutation.isPending}
              >
                <NumberInputField />
                <NumberInputStepper>
                  <NumberIncrementStepper />
                  <NumberDecrementStepper />
                </NumberInputStepper>
              </NumberInput>
              <FormHelperText>
                {formatMessage({ id: 'settings.chunk_overlap.help' })}
              </FormHelperText>
            </FormControl>

            <FormControl>
              <FormLabel>
                {formatMessage({ id: 'settings.similarity_threshold' })}: {formData.similarity_threshold.toFixed(1)}
              </FormLabel>
              <Slider
                aria-label={formatMessage({ id: 'settings.similarity_threshold' })}
                value={formData.similarity_threshold}
                onChange={(value) => setFormData({ ...formData, similarity_threshold: value })}
                min={0}
                max={1}
                step={0.1}
                isDisabled={updateMutation.isPending}
              >
                <SliderTrack>
                  <SliderFilledTrack />
                </SliderTrack>
                <SliderThumb aria-label={formatMessage({ id: 'settings.similarity_threshold' })} />
              </Slider>
              <FormHelperText>
                {formatMessage({ id: 'settings.similarity_threshold.help' })}
              </FormHelperText>
            </FormControl>

            <FormControl>
              <FormLabel>{formatMessage({ id: 'settings.top_k_results' })}</FormLabel>
              <NumberInput
                aria-label={formatMessage({ id: 'settings.top_k_results' })}
                value={formData.top_k_results}
                onChange={(_, value) => setFormData({ ...formData, top_k_results: value || 1 })}
                min={1}
                max={20}
                isDisabled={updateMutation.isPending}
              >
                <NumberInputField />
                <NumberInputStepper>
                  <NumberIncrementStepper />
                  <NumberDecrementStepper />
                </NumberInputStepper>
              </NumberInput>
              <FormHelperText>
                {formatMessage({ id: 'settings.top_k_results.help' })}
              </FormHelperText>
            </FormControl>
          </VStack>
        </Box>

        <Divider />

        <Box>
          <Heading size="sm" mb={4}>
            {formatMessage({ id: 'settings.section.llm' })}
          </Heading>
          <VStack spacing={4} align="stretch">
            <FormControl>
              <FormLabel>{formatMessage({ id: 'settings.llm_provider' })}</FormLabel>
              <Select
                aria-label={formatMessage({ id: 'settings.llm_provider' })}
                value={formData.llm_provider}
                onChange={(e) =>
                  setFormData({
                    ...formData,
                    llm_provider: e.target.value as SystemSettings['llm_provider'],
                  })
                }
                isDisabled={updateMutation.isPending}
              >
                <option value="openai">OpenAI</option>
                <option value="anthropic">Anthropic</option>
                <option value="ollama">Ollama</option>
              </Select>
            </FormControl>

            <FormControl>
              <FormLabel>{formatMessage({ id: 'settings.embedding_provider' })}</FormLabel>
              <Select
                aria-label={formatMessage({ id: 'settings.embedding_provider' })}
                value={formData.embedding_provider}
                onChange={(e) =>
                  setFormData({
                    ...formData,
                    embedding_provider: e.target.value as SystemSettings['embedding_provider'],
                  })
                }
                isDisabled={updateMutation.isPending}
              >
                <option value="openai">OpenAI</option>
                <option value="local">Local</option>
              </Select>
            </FormControl>

            <FormControl>
              <FormLabel>{formatMessage({ id: 'settings.embedding_model' })}</FormLabel>
              <Input
                aria-label={formatMessage({ id: 'settings.embedding_model' })}
                value={formData.embedding_model}
                onChange={(e) => setFormData({ ...formData, embedding_model: e.target.value })}
                isDisabled={updateMutation.isPending}
              />
            </FormControl>
          </VStack>
        </Box>

        <Button
          type="submit"
          colorScheme="blue"
          isLoading={updateMutation.isPending}
          alignSelf="flex-start"
        >
          {formatMessage({ id: 'settings.save' })}
        </Button>
      </VStack>
    </Box>
  );
};
