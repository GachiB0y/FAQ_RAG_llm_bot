import { Button, ButtonGroup, HStack, Select, Text } from '@chakra-ui/react';
import type { PostsTablePaginationProps } from '@features/posts-table/model';

export const PostsTablePagination = ({
  page,
  totalPages,
  pageSize,
  pageSizeOptions,
  onPageChange,
  onPageSizeChange,
  infoText,
  rowsPerPageLabel,
  prevLabel,
  nextLabel,
}: PostsTablePaginationProps) => {
  const handlePrev = () => onPageChange(Math.max(1, page - 1));

  const handleNext = () => onPageChange(Math.min(totalPages || 1, page + 1));

  return (
    <HStack justify="space-between" flexWrap="wrap" gap={4}>
      <HStack>
        <Text fontSize="sm" color="text.secondary">
          {rowsPerPageLabel}
        </Text>
        <Select
          maxW="90px"
          value={pageSize}
          onChange={(event) => onPageSizeChange(Number(event.target.value))}
        >
          {pageSizeOptions.map((option) => (
            <option key={option} value={option}>
              {option}
            </option>
          ))}
        </Select>
      </HStack>
      <HStack>
        <Text fontSize="sm" color="text.secondary">
          {infoText}
        </Text>
        <ButtonGroup variant="ghost" size="sm" isAttached>
          <Button onClick={handlePrev} isDisabled={page === 1 || totalPages === 0}>
            {prevLabel}
          </Button>
          <Button onClick={handleNext} isDisabled={totalPages === 0 || page >= totalPages}>
            {nextLabel}
          </Button>
        </ButtonGroup>
      </HStack>
    </HStack>
  );
};
