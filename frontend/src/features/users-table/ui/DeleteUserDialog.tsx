import { useRef } from 'react';
import { useIntl } from 'react-intl';
import {
  AlertDialog,
  AlertDialogBody,
  AlertDialogContent,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogOverlay,
  Button,
} from '@chakra-ui/react';
import type { User } from '@entities/user';

interface DeleteUserDialogProps {
  isOpen: boolean;
  onClose: () => void;
  user: User | null;
  onConfirm: () => void;
  isLoading: boolean;
}

export const DeleteUserDialog = ({
  isOpen,
  onClose,
  user,
  onConfirm,
  isLoading,
}: DeleteUserDialogProps) => {
  const { formatMessage } = useIntl();
  const cancelRef = useRef<HTMLButtonElement>(null!);

  return (
    <AlertDialog
      isOpen={isOpen}
      leastDestructiveRef={cancelRef}
      onClose={onClose}
    >
      <AlertDialogOverlay>
        <AlertDialogContent>
          <AlertDialogHeader>
            {formatMessage({ id: 'users.delete.title' })}
          </AlertDialogHeader>
          <AlertDialogBody>
            {user &&
              formatMessage(
                { id: 'users.delete.confirm' },
                { email: user.email },
              )}
          </AlertDialogBody>
          <AlertDialogFooter>
            <Button ref={cancelRef} onClick={onClose}>
              {formatMessage({ id: 'users.form.cancel' })}
            </Button>
            <Button
              colorScheme="red"
              onClick={onConfirm}
              ml={3}
              isLoading={isLoading}
            >
              {formatMessage({ id: 'users.action.delete' })}
            </Button>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialogOverlay>
    </AlertDialog>
  );
};
