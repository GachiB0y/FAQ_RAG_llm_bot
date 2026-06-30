import { useEffect, useState } from 'react';
import { useIntl } from 'react-intl';
import {
  Button,
  FormControl,
  FormErrorMessage,
  FormLabel,
  Input,
  Modal,
  ModalBody,
  ModalCloseButton,
  ModalContent,
  ModalFooter,
  ModalHeader,
  ModalOverlay,
  Select,
  Switch,
  useToast,
  VStack,
} from '@chakra-ui/react';
import type { User, UserUpdate } from '@entities/user';
import { useUpdateUser } from '@entities/user';

interface UserFormData {
  email: string;
  password: string;
  role: 'admin' | 'user';
  is_active: boolean;
}

interface EditUserModalProps {
  isOpen: boolean;
  onClose: () => void;
  user: User | null;
}

export const EditUserModal = ({
  isOpen,
  onClose,
  user,
}: EditUserModalProps) => {
  const { formatMessage } = useIntl();
  const toast = useToast();
  const updateMutation = useUpdateUser();

  const [formData, setFormData] = useState<UserFormData>({
    email: '',
    password: '',
    role: 'user',
    is_active: true,
  });
  const [errors, setErrors] = useState<{ email?: string; password?: string }>(
    {},
  );

  useEffect(() => {
    if (user && isOpen) {
      setFormData({
        email: user.email,
        password: '',
        role: user.role,
        is_active: user.is_active,
      });
      setErrors({});
    }
  }, [user, isOpen]);

  const resetForm = () => {
    if (user) {
      setFormData({
        email: user.email,
        password: '',
        role: user.role,
        is_active: user.is_active,
      });
    }
    setErrors({});
  };

  const validateForm = (): boolean => {
    const newErrors: { email?: string; password?: string } = {};
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

    if (!emailRegex.test(formData.email)) {
      newErrors.email = formatMessage({ id: 'users.validation.email.invalid' });
    }
    if (formData.password && formData.password.length < 6) {
      newErrors.password = formatMessage({ id: 'users.validation.password.min' });
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async () => {
    if (!user || !validateForm()) return;

    const data: UserUpdate = {
      email: formData.email,
      role: formData.role,
      is_active: formData.is_active,
    };

    if (formData.password) {
      data.password = formData.password;
    }

    try {
      await updateMutation.mutateAsync({ id: user.id, data });
      toast({
        title: formatMessage({ id: 'users.update.success' }),
        status: 'success',
        duration: 3000,
      });
      onClose();
    } catch {
      toast({
        title: formatMessage({ id: 'users.update.error' }),
        status: 'error',
        duration: 3000,
      });
    }
  };

  const handleClose = () => {
    setErrors({});
    onClose();
  };

  return (
    <Modal isOpen={isOpen} onClose={handleClose} onCloseComplete={resetForm}>
      <ModalOverlay />
      <ModalContent>
        <ModalHeader>{formatMessage({ id: 'users.edit.title' })}</ModalHeader>
        <ModalCloseButton />
        <ModalBody>
          <VStack spacing={4}>
            <FormControl isInvalid={!!errors.email} isRequired>
              <FormLabel>{formatMessage({ id: 'users.form.email' })}</FormLabel>
              <Input
                type="email"
                value={formData.email}
                onChange={(e) =>
                  setFormData({ ...formData, email: e.target.value })
                }
              />
              <FormErrorMessage>{errors.email}</FormErrorMessage>
            </FormControl>
            <FormControl isInvalid={!!errors.password}>
              <FormLabel>
                {formatMessage({ id: 'users.form.password' })}
              </FormLabel>
              <Input
                type="password"
                value={formData.password}
                onChange={(e) =>
                  setFormData({ ...formData, password: e.target.value })
                }
                placeholder={formatMessage({ id: 'users.form.password.hint' })}
              />
              <FormErrorMessage>{errors.password}</FormErrorMessage>
            </FormControl>
            <FormControl>
              <FormLabel>{formatMessage({ id: 'users.form.role' })}</FormLabel>
              <Select
                value={formData.role}
                onChange={(e) =>
                  setFormData({
                    ...formData,
                    role: e.target.value as 'admin' | 'user',
                  })
                }
              >
                <option value="user">
                  {formatMessage({ id: 'users.role.user' })}
                </option>
                <option value="admin">
                  {formatMessage({ id: 'users.role.admin' })}
                </option>
              </Select>
            </FormControl>
            <FormControl display="flex" alignItems="center">
              <FormLabel mb={0}>
                {formatMessage({ id: 'users.form.isActive' })}
              </FormLabel>
              <Switch
                isChecked={formData.is_active}
                onChange={(e) =>
                  setFormData({ ...formData, is_active: e.target.checked })
                }
              />
            </FormControl>
          </VStack>
        </ModalBody>
        <ModalFooter>
          <Button variant="ghost" mr={3} onClick={handleClose}>
            {formatMessage({ id: 'users.form.cancel' })}
          </Button>
          <Button
            colorScheme="blue"
            onClick={handleSubmit}
            isLoading={updateMutation.isPending}
          >
            {formatMessage({ id: 'users.form.save' })}
          </Button>
        </ModalFooter>
      </ModalContent>
    </Modal>
  );
};
