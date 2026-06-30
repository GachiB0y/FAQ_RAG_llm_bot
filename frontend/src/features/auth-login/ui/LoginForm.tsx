import { useState } from 'react';
import { useIntl } from 'react-intl';
import { useNavigate } from 'react-router-dom';
import {
  Alert,
  AlertIcon,
  Box,
  Button,
  Card,
  CardBody,
  FormControl,
  FormLabel,
  Heading,
  Input,
  VStack,
} from '@chakra-ui/react';
import { useAuthStore } from '@entities/auth';
import { authApi } from '@shared/api';

export const LoginForm = () => {
  const { formatMessage } = useIntl();
  const navigate = useNavigate();
  const setAuth = useAuthStore((state) => state.setAuth);

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      await authApi.login({ email, password });
      // Decode JWT to get user info (simplified - in production use proper JWT decode)
      setAuth({ email, role: 'admin' });
      navigate('/admin/documents');
    } catch (err) {
      setError(formatMessage({ id: 'auth.login.error' }));
    } finally {
      setLoading(false);
    }
  };

  return (
    <Box minH="100vh" display="flex" alignItems="center" justifyContent="center" bg="gray.50" _dark={{ bg: 'gray.900' }}>
      <Card maxW="md" w="full" mx={4}>
        <CardBody>
          <VStack spacing={6} as="form" onSubmit={handleSubmit}>
            <Heading size="lg">{formatMessage({ id: 'auth.login.title' })}</Heading>

            {error && (
              <Alert status="error" borderRadius="md">
                <AlertIcon />
                {error}
              </Alert>
            )}

            <FormControl isRequired>
              <FormLabel>{formatMessage({ id: 'auth.login.email' })}</FormLabel>
              <Input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="admin@example.com"
              />
            </FormControl>

            <FormControl isRequired>
              <FormLabel>{formatMessage({ id: 'auth.login.password' })}</FormLabel>
              <Input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
            </FormControl>

            <Button
              type="submit"
              colorScheme="blue"
              w="full"
              isLoading={loading}
            >
              {formatMessage({ id: 'auth.login.submit' })}
            </Button>
          </VStack>
        </CardBody>
      </Card>
    </Box>
  );
};
