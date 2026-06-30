import { useState } from 'react';
import { useIntl } from 'react-intl';
import { DeleteIcon, EditIcon } from '@chakra-ui/icons';
import {
  Alert,
  AlertIcon,
  Badge,
  Button,
  HStack,
  IconButton,
  Skeleton,
  Switch,
  Table,
  Tbody,
  Td,
  Text,
  Th,
  Thead,
  Tr,
  useDisclosure,
  useToast,
} from '@chakra-ui/react';
import type { User } from '@entities/user';
import {
  useDeleteUser,
  useUpdateUser,
  useUsers,
} from '@entities/user';

import { CreateUserModal } from './CreateUserModal';
import { DeleteUserDialog } from './DeleteUserDialog';
import { EditUserModal } from './EditUserModal';

const RoleBadge = ({ role }: { role: User['role'] }) => {
  const { formatMessage } = useIntl();
  const colorScheme = role === 'admin' ? 'purple' : 'blue';
  const label = formatMessage({ id: `users.role.${role}` });

  return <Badge colorScheme={colorScheme}>{label}</Badge>;
};

const StatusBadge = ({ isActive }: { isActive: boolean }) => {
  const { formatMessage } = useIntl();
  const colorScheme = isActive ? 'green' : 'gray';
  const label = formatMessage({
    id: isActive ? 'users.status.active' : 'users.status.inactive',
  });

  return <Badge colorScheme={colorScheme}>{label}</Badge>;
};

export const UsersTable = () => {
  const { formatMessage } = useIntl();
  const toast = useToast();
  const createModal = useDisclosure();
  const editModal = useDisclosure();
  const deleteDialog = useDisclosure();
  const [editingUser, setEditingUser] = useState<User | null>(null);
  const [userToDelete, setUserToDelete] = useState<User | null>(null);

  const { data: users, isLoading, error } = useUsers();
  const deleteMutation = useDeleteUser();
  const updateMutation = useUpdateUser();

  const handleEdit = (user: User) => {
    setEditingUser(user);
    editModal.onOpen();
  };

  const handleToggleActive = async (user: User) => {
    try {
      await updateMutation.mutateAsync({
        id: user.id,
        data: { is_active: !user.is_active },
      });
      toast({
        title: formatMessage({ id: 'users.update.success' }),
        status: 'success',
        duration: 3000,
      });
    } catch {
      toast({
        title: formatMessage({ id: 'users.update.error' }),
        status: 'error',
        duration: 3000,
      });
    }
  };

  const handleDeleteClick = (user: User) => {
    setUserToDelete(user);
    deleteDialog.onOpen();
  };

  const handleDeleteConfirm = async () => {
    if (!userToDelete) return;
    try {
      await deleteMutation.mutateAsync(userToDelete.id);
      toast({
        title: formatMessage({ id: 'users.delete.success' }),
        status: 'success',
        duration: 3000,
      });
    } catch {
      toast({
        title: formatMessage({ id: 'users.delete.error' }),
        status: 'error',
        duration: 3000,
      });
    }
    deleteDialog.onClose();
    setUserToDelete(null);
  };

  if (isLoading) {
    return (
      <>
        {[1, 2, 3].map((i) => (
          <Skeleton key={i} height="50px" mb={2} />
        ))}
      </>
    );
  }

  if (error) {
    return (
      <Alert status="error">
        <AlertIcon />
        {formatMessage({ id: 'users.error.load' })}
      </Alert>
    );
  }

  if (!users?.length) {
    return (
      <>
        <HStack mb={4} justifyContent="flex-end">
          <Button colorScheme="blue" onClick={createModal.onOpen}>
            {formatMessage({ id: 'users.create.button' })}
          </Button>
        </HStack>
        <Alert status="info">
          <AlertIcon />
          {formatMessage({ id: 'users.empty' })}
        </Alert>
        <CreateUserModal
          isOpen={createModal.isOpen}
          onClose={createModal.onClose}
        />
      </>
    );
  }

  return (
    <>
      <HStack mb={4} justifyContent="flex-end">
        <Button colorScheme="blue" onClick={createModal.onOpen}>
          {formatMessage({ id: 'users.create.button' })}
        </Button>
      </HStack>
      <Table variant="simple">
        <Thead>
          <Tr>
            <Th>{formatMessage({ id: 'users.table.email' })}</Th>
            <Th>{formatMessage({ id: 'users.table.role' })}</Th>
            <Th>{formatMessage({ id: 'users.table.status' })}</Th>
            <Th>{formatMessage({ id: 'users.table.created' })}</Th>
            <Th>{formatMessage({ id: 'users.table.actions' })}</Th>
          </Tr>
        </Thead>
        <Tbody>
          {users.map((user) => (
            <Tr key={user.id}>
              <Td>
                <Text fontWeight="medium">{user.email}</Text>
              </Td>
              <Td>
                <RoleBadge role={user.role} />
              </Td>
              <Td>
                <StatusBadge isActive={user.is_active} />
              </Td>
              <Td>{new Date(user.created_at).toLocaleDateString()}</Td>
              <Td>
                <HStack spacing={2}>
                  <IconButton
                    aria-label={formatMessage({ id: 'users.action.edit' })}
                    icon={<EditIcon />}
                    size="sm"
                    variant="ghost"
                    onClick={() => handleEdit(user)}
                  />
                  <Switch
                    aria-label={formatMessage({ id: 'users.action.toggle' })}
                    isChecked={user.is_active}
                    onChange={() => handleToggleActive(user)}
                    size="sm"
                  />
                  <IconButton
                    aria-label={formatMessage({ id: 'users.action.delete' })}
                    icon={<DeleteIcon />}
                    size="sm"
                    variant="ghost"
                    colorScheme="red"
                    onClick={() => handleDeleteClick(user)}
                  />
                </HStack>
              </Td>
            </Tr>
          ))}
        </Tbody>
      </Table>
      <CreateUserModal
        isOpen={createModal.isOpen}
        onClose={createModal.onClose}
      />
      <EditUserModal
        isOpen={editModal.isOpen}
        onClose={editModal.onClose}
        user={editingUser}
      />
      <DeleteUserDialog
        isOpen={deleteDialog.isOpen}
        onClose={deleteDialog.onClose}
        user={userToDelete}
        onConfirm={handleDeleteConfirm}
        isLoading={deleteMutation.isPending}
      />
    </>
  );
};
