import { type SectionConfig } from '@pages/home/model/types';

const techMessages: SectionConfig['messages'] = [
  'stack.ui',
  'stack.state',
  'stack.data',
  'stack.i18n',
  'stack.style',
];

const architectureMessages: SectionConfig['messages'] = ['arch.layers', 'arch.fsd'];

const setupMessages: SectionConfig['messages'] = ['setup.commands', 'setup.precommit'];

export const HOME_SECTIONS: SectionConfig[] = [
  {
    titleId: 'section.tech.title',
    descriptionId: 'section.tech.description',
    messages: techMessages,
  },
  {
    titleId: 'section.arch.title',
    descriptionId: 'section.arch.description',
    messages: architectureMessages,
  },
  {
    titleId: 'section.setup.title',
    descriptionId: 'section.setup.description',
    messages: setupMessages,
  },
];
