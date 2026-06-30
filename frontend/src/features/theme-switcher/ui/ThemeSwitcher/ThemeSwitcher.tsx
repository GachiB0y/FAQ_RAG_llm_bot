import { useIntl } from 'react-intl';
import { MoonIcon, SunIcon } from '@chakra-ui/icons';
import { IconButton, Tooltip, useColorMode } from '@chakra-ui/react';
import { motion } from '@shared/lib';

const MotionIconButton = motion(IconButton);
const MotionIconWrapper = motion.span;

export const ThemeSwitcher = () => {
  const { formatMessage } = useIntl();
  const { colorMode, toggleColorMode } = useColorMode();

  const isDarkMode = colorMode === 'dark';
  const label = isDarkMode
    ? formatMessage({ id: 'action.theme.light' })
    : formatMessage({ id: 'action.theme.dark' });

  return (
    <Tooltip label={label} hasArrow>
      <MotionIconButton
        aria-label={label}
        icon={
          <MotionIconWrapper
            key={colorMode}
            initial={{ rotate: -35, opacity: 0, scale: 0.9 }}
            animate={{ rotate: 0, opacity: 1, scale: 1 }}
            transition={{ duration: 0.25, ease: 'easeOut' }}
          >
            {isDarkMode ? <SunIcon /> : <MoonIcon />}
          </MotionIconWrapper>
        }
        onClick={toggleColorMode}
        size="sm"
        variant="ghost"
        whileHover={{ scale: 1.05 }}
        whileTap={{ scale: 0.95 }}
      />
    </Tooltip>
  );
};
