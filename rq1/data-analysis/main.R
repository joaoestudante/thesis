# Graphical analysis of some characteristics of repos and results of the
# simpler logical coupling.

library(ggplot2)
library(ggrepel)

data <- read.csv("../data/logical-coupling-comparison-data.csv")
pairs_frequency_data <- read.csv("../data/pairs-frequencies.csv")

# Plot covered pairs against the number of selected commits
pairs_covered_in_percentage <- data$pairs_covered/data$total_pairs
ggplot(data, aes(x=ncommits, y=pairs_covered_in_percentage, label=name)) +
  geom_point() +
  geom_label(hjust=-0.1) +
  scale_x_continuous(n.breaks = 15, limits = c(0, 30000)) +
  scale_y_continuous(n.breaks = 15) +
  ylab("Pairs covered (%)") +
  xlab("Number of commits") +
  ggtitle("Percentage of .java files pairs that changed together, vs the number of commits")

# Plot covered pairs against the number of files
ggplot(data, aes(x=nfiles, y=pairs_covered_in_percentage, label=name)) +
  geom_point() +
  geom_label_repel(min.segment.length = 0) +
  scale_x_continuous(n.breaks = 15, limits = c(0, 35000)) +
  scale_y_continuous(n.breaks = 15) +
  ylab("Pairs covered (%)") +
  xlab("Number of files") +
  ggtitle("Percentage of .java files pairs that changed together, vs the number of files in the project")

# Plot number of files vs number of commits
ggplot(data, aes(x=nfiles, y=ncommits, label=name)) +
  geom_point() +
  geom_label_repel(min.segment.length = 0) +
  scale_x_continuous(n.breaks = 15, limits = c(0, 35000)) +
  scale_y_continuous(n.breaks = 15, limits = c(0, 35000)) +
  ylab("Number of commits") +
  xlab("Number of files") +
  ggtitle("Number of commits vs the number of files in the project")


# Plot the frequency of pairs
ggplot(pairs_frequency_data[pairs_frequency_data$count > 0.0001,], aes(x=frequency, y=count)) +
  geom_bar(stat="identity") +
  facet_wrap(~name, scales="free") +
  xlab("Number of times pairs appear together") +
  ylab("% of pairs") +
  ggtitle("Number of times percentages of pairs change together")
# pairs_frequency_expanded <- pairs_frequency_data[rep(row.names(pairs_frequency_data), pairs_frequency_data$count), 1:2]
# ggplot(pairs_frequency_data, aes(x=name,y=frequency)) +
#   geom_boxplot() +
#   facet_wrap(~name, scales="free")

# Plot the pairs that show up once and more than once, for each project

# Reorganize data so that we have the occurrences in different rows rather than in different columns
total_data_pivoted <- tidyr::pivot_longer(data, cols=c('total_pairs', 'pairs_occurring_once', 'pairs_occurring_more_than_once'), names_to='variable', 
                           values_to="value")
changing_pairs_pivoted <- tidyr::pivot_longer(data, cols=c('pairs_occurring_once', 'pairs_occurring_more_than_once'), names_to='variable', 
                          values_to="value")

ggplot(total_data_pivoted, aes(x=name, y=value, fill=variable)) +
  geom_bar(stat='identity', position='fill') + # change position to "dodge" for grouped bar chart
  ylab("Percentage of pairs that change together") +
  xlab("Project name") +
  scale_fill_discrete(name = "Legend:", labels = c("Changed together more\n than once", "Changed together once", "Never changed together")) +
  ggtitle("Percentage of pairs that change together just once,\nmore than once, and never") +
  theme(axis.text.x = element_text(angle = 45, hjust=1))

ggplot(changing_pairs_pivoted, aes(x=name, y=value, fill=variable)) +
  geom_bar(stat='identity', position='fill') + # change position to "dodge" for grouped bar chart
  ylab("Percentage of pairs that change together") +
  xlab("Project name") +
  scale_fill_discrete(name = "Legend:", labels = c("Changed together more\n than once", "Changed together once")) +
  ggtitle("Percentage of pairs that change together just once,\nand more than once") +
  theme(axis.text.x = element_text(angle = 45, hjust=1))
