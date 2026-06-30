import {
  Alert,
  AlertDescription,
  AlertIcon,
  AlertTitle,
  Button,
  Card,
  CardBody,
  Stack,
} from '@chakra-ui/react';
import type { PostsTableErrorProps } from '@features/posts-table/model';

export const PostsTableError = ({
  title,
  description,
  actionLabel,
  onRetry,
  isLoading,
}: PostsTableErrorProps) => (
  <Card bg="bg.surface" border="1px solid" borderColor="border.default">
    <CardBody>
      <Alert status="error" variant="left-accent" bg="transparent">
        <AlertIcon />
        <Stack spacing={2}>
          <AlertTitle>{title}</AlertTitle>
          <AlertDescription>{description}</AlertDescription>
          <Button onClick={onRetry} isLoading={isLoading} maxW="fit-content">
            {actionLabel}
          </Button>
        </Stack>
      </Alert>
    </CardBody>
  </Card>
);
