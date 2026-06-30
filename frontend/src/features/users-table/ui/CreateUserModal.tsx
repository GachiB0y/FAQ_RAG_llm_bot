import { useState } from 'react';
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
  useToast,
  VStack,
} from '@chakra-ui/react';
import type { UserCreate } from '@entities/user';
import { useCreateUser } from '@entities/user';

interface UserFormData {
  email: string;
  password: string;
  role: 'admin' | 'user';
}

interface CreateUserModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export const CreateUserModal = ({ isOpen, onClose }: CreateUserModalProps) => {
  const { formatMessage } = useIntl();
  const toast = useToast();
  const createMutation = useCreateUser();

  const [formData, setFormData] = useState<UserFormData>({
    email: '',
    password: '',
    role: 'user',
  });
  const [errors, setErrors] = useState<{ email?: string; password?: string }>(
    {},
  );

  const validateForm = (): boolean => {
    const newErrors: { email?: string; password?: string } = {};
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

    if (!emailRegex.test(formData.email)) {
      newErrors.email = formatMessage({ id: 'users.validation.email.invalid' });
    }
    if (formData.password.length < 6) {
      newErrors.password = formatMessage({ id: 'users.validation.password.min' });
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async () => {
    if (!validateForm()) return;

    const data: UserCreate = {
      email: formData.email,
      password: formData.password,
      role: formData.role,
    };

    try {
      await createMutation.mutateAsync(data);
      toast({
        title: formatMessage({ id: 'users.create.success' }),
        status: 'success',
        duration: 3000,
      });
      onClose();
      setFormData({ email: '', password: '', role: 'user' });
      setErrors({});
    } catch {
      toast({
        title: formatMessage({ id: 'users.create.error' }),
        status: 'error',
        duration: 3000,
      });
    }
  };

  const handleClose = () => {
    setFormData({ email: '', password: '', role: 'user' });
    setErrors({});
    onClose();
  };

  return (
    <Modal isOpen={isOpen} onClose={handleClose}>
      <ModalOverlay />
      <ModalContent>
        <ModalHeader>{formatMessage({ id: 'users.create.title' })}</ModalHeader>
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
            <FormControl isInvalid={!!errors.password} isRequired>
              <FormLabel>
                {formatMessage({ id: 'users.form.password' })}
              </FormLabel>
              <Input
                type="password"
                value={formData.password}
                onChange={(e) =>
                  setFormData({ ...formData, password: e.target.value })
                }
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
          </VStack>
        </ModalBody>
        <ModalFooter>
          <Button variant="ghost" mr={3} onClick={handleClose}>
            {formatMessage({ id: 'users.form.cancel' })}
          </Button>
          <Button
            colorScheme="blue"
            onClick={handleSubmit}
            isLoading={createMutation.isPending}
          >
            {formatMessage({ id: 'users.form.create' })}
          </Button>
        </ModalFooter>
      </ModalContent>
    </Modal>
  );
};
