import { useIntl } from 'react-intl';
import { Container, Divider, Heading, Stack, Text } from '@chakra-ui/react';
import { HOME_SECTIONS } from '@pages/home/config';
import { fadeInUp, motion, staggerChildren } from '@shared/lib';

import { SectionCard } from './SectionCard';

import styles from './HomePage.module.scss';

export const HomePage = () => {
  const { formatMessage } = useIntl();

  return (
    <div className={styles.root}>
      <Container maxW="6xl">
        <Stack spacing={6} align="flex-start">
          <Stack spacing={3} w="full">
            <Heading as="h1" size="xl">
              {formatMessage({ id: 'app.title' })}
            </Heading>
            <Text color="gray.300">{formatMessage({ id: 'app.subtitle' })}</Text>
          </Stack>
          <Divider borderColor="whiteAlpha.300" />
          <motion.div
            className={styles.sectionGrid}
            variants={staggerChildren}
            initial="hidden"
            animate="visible"
          >
            {HOME_SECTIONS.map((section) => (
              <motion.div key={section.titleId} variants={fadeInUp}>
                <SectionCard {...section} formatMessage={formatMessage} />
              </motion.div>
            ))}
          </motion.div>
        </Stack>
      </Container>
    </div>
  );
};
