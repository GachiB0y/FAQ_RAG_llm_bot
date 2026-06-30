import { type IntlShape } from 'react-intl';

export type SectionConfig = {
  titleId: string;
  descriptionId: string;
  messages: string[];
};

export type SectionCardProps = SectionConfig & {
  formatMessage: IntlShape['formatMessage'];
};
