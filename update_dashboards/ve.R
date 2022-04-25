#!/usr/bin/env Rscript

# script is intended for running from base dir `/logistics`
# normalizePath(".")

rm(list = ls())
suppressPackageStartupMessages({
  library(tidyverse)
  library(cdcfluview)
  library(zoo)
})

"%notin%" <- Negate("%in%")

# setwd("data/id3c_scan_vaccine_data.csv")
# setwd("C:/Users/hansencl/OneDrive - National Institutes of Health/SFS/VE dashboard")

# Exclusion Criteria
# Must be King County
# Must be Community Enrollment
# Must have a test result
# Must be over 12 - (vaccines extended to 5yrs and up on November 2)
# date_last_covid_dose must be after 2020-12-01 and before the encountered date


# Prep Data ------------------------------------------------------
other_vax <- c("astrazeneca", "dont_know", "dont_say", "novavax", "other")

dat <- read.csv("data/id3c_scan_vaccine_data.csv") %>%
  mutate(
    encountered = as.Date(encountered),
    date_last_covid_dose = as.Date(date_last_covid_dose),
    vaccination_status = as.character(vaccination_status),
    number_of_covid_doses = as.character(number_of_covid_doses)
  ) %>%
  filter(
    encountered >= "2021-01-20" &
      enrollment_method == "Community Enrollment" &
      # date_last_covid_dose <= encountered &
      age >= 12 &
      # (date_last_covid_dose >= '2020-12-01'|date_last_covid_dose=="") &
      (region == "South King County" | region == "North King County"),
    vac_name_1 %notin% other_vax, vac_name_2 %notin% other_vax, vac_name_3 %notin% other_vax
  ) %>%
  mutate(
    mmwr_week(encountered),
    week_date = mmwr_week_to_date(mmwr_year, mmwr_week),
    week_num = dense_rank(week_date),
    case_control = factor(hcov19_result, levels = c("Positive", "Inconclusive", "Negetive"), labels = c("case", "case", "control")),
    case_control_bin = ifelse(hcov19_result == "Positive" | hcov19_result == "Inconclusive", 1,
      ifelse(hcov19_result == "Negetive", 0, NA)
    ),
    delta_case = ifelse(case_control_bin == 1 & s_gene == "S gene negative", 1,
      ifelse(case_control_bin == 0, 0, NA)
    ),
    omicron_case = ifelse(case_control_bin == 1 & s_gene == "S gene positive" & encountered >= "2021-10-01", 1,
      ifelse(case_control_bin == 0, 0, NA)
    ),
    alpha = ifelse(encountered >= "2021-04-11" & encountered < "2021-06-20", 1, 0),
    delta = ifelse(encountered >= "2021-06-20" & encountered < "2021-12-12", 1, 0),
    omicron = ifelse(encountered >= "2021-12-12" & encountered <= Sys.Date(), 1, 0),
    variant_indicator = ifelse(alpha == 1, "alpha",
      ifelse(delta == 1, "delta",
        ifelse(omicron == 1, "omicron", "other")
      )
    ),
    variant_indicator = factor(variant_indicator, levels = c("other", "alpha", "delta", "omicron")),
    variant_indicator2 = ifelse(delta == 1, "delta",
      ifelse(omicron == 1, "omicron", "other")
    ),
    variant_indicator2 = factor(variant_indicator, levels = c("other", "delta", "omicron")),
    prior_infection = ifelse(grepl("yes", prior_test_positive), 1, 0),
    time_since_vax = as.numeric(difftime(encountered, date_last_covid_dose, units = "days")),
    doses_recode = ifelse(number_of_covid_doses == "2_doses" & (time_since_vax > 180 | is.na(time_since_vax)), "2_doses_>6m",
      ifelse(number_of_covid_doses == "2_doses" & time_since_vax <= 180, "2_doses_<6m", number_of_covid_doses)
    ),
    doses_recode = factor(doses_recode, levels = c("unknown", "0_doses", "1_dose", "2_doses_>6m", "2_doses_<6m", "3_doses")),
    regression_doses = factor(doses_recode,
      levels = c("unknown", "0_doses", "1_dose", "2_doses_>6m", "2_doses_<6m", "3_doses"),
      labels = c("reference", "reference", "reference", "2_doses_>6m", "2_doses_<6m", "3_doses")
    ), # combining unknown, 0 and 1 doses
    fully_vaccinated = ifelse(vaccination_status == "fully_vaccinated" | vaccination_status == "boosted", "yes", "no"), # includes boosted people
    fully_boosted = ifelse(vaccination_status == "boosted", "yes",
      ifelse(vaccination_status == "fully_vaccinated", "no", NA)
    ),
    vax_status = ifelse(vaccination_status == "not_vaccinated" | vaccination_status == "partially_vaccinated" | vaccination_status == "unknown", "not_fully", vaccination_status),
    vax_status = factor(vax_status, levels = c("not_fully", "fully_vaccinated", "boosted")),
    sex = factor(sex, levels = c("female", "male")),
    race_ethnicity_recode = factor(race_ethnicity,
      levels = c(
        "White, not Hispanic", "Asian, not Hispanic", "Black, not Hispanic", "Hispanic or Latino, any Race",
        "Amer. Indian or Alaska Native", "NH/OPI", "Other/Multi, Non Hisp.", ""
      ),
      labels = c("White", "Asian", "Black", "Hispanic", "Other", "Other", "Other", "Other")
    ),
    age_group = ifelse(age >= 12 & age < 25, "age_12_to_25",
      ifelse(age >= 25 & age < 35, "age_25_to_35",
        ifelse(age >= 35 & age < 50, "age_35_to_50", "over_50")
      )
    )
  ) %>%
  filter(!is.na(case_control), vaccination_status != "unknown")

# SCAN participants by vaccine doses  --------------------------------

scan_vax_dose <- dat %>%
  group_by(week_date, doses_recode) %>%
  tally() %>%
  ungroup() %>%
  mutate(
    doses_recode = as.character(doses_recode),
    doses_recode = ifelse(is.na(doses_recode), "unknown", doses_recode),
    doses_recode = factor(doses_recode,
      levels = c("3_doses", "2_doses_<6m", "2_doses_>6m", "1_dose", "0_doses", "unknown"),
      labels = c("3 Doses", "2 Doses <6m ago", "2 Doses >6m ago", "1 Dose", "0 Doses", "Unknown")
    )
  )

write.csv(scan_vax_dose, "data/vaccine_doses.csv", row.names = F)
# These dataframe is used to make the vaccine doses over time plot

scan_vax_status <- dat %>%
  group_by(week_date, vax_status) %>%
  tally() %>%
  ungroup() %>%
  pivot_wider(names_from = vax_status, values_from = n) %>%
  replace(is.na(.), 0) %>%
  mutate(
    not_roll = rollapplyr(rowSums(.[, 2]), 9, sum, partial = TRUE),
    fully_roll = rollapplyr(rowSums(.[, 3]), 9, sum, partial = TRUE),
    boost_roll = rollapplyr(rowSums(.[, 4]), 9, sum, partial = TRUE),
    total = not_roll + fully_roll + boost_roll,
    prop_not = not_roll / total,
    prop_fully = fully_roll / total,
    prop_boost = boost_roll / total
  ) %>%
  pivot_longer(cols = c(prop_not, prop_fully, prop_boost), names_to = "status", values_to = "prop") %>%
  select(week_date, status, prop)

write.csv(scan_vax_status, "data/vaccination_status.csv", row.names = F)
# This dataframe is used to make the vaccination status over time plot (bottom plot tab 1)


# Screening Method - DATA prep--------------------------------------------------------
# for any fully vaccinated (this also includes booster)
screening_data <- dat %>%
  filter(week_date >= "2021-01-24") %>%
  group_by(week_date, case_control, fully_vaccinated) %>%
  tally() %>%
  ungroup() %>%
  pivot_wider(id_cols = week_date, names_from = c(case_control, fully_vaccinated), values_from = n) %>%
  replace(is.na(.), 0) %>%
  # summing over 6-week windows
  mutate(
    total = rollapplyr(rowSums(.[, 2:5]), 9, sum, partial = TRUE),
    vax_total = rollapplyr(rowSums(.[grep("yes", names(.))]), 9, sum, partial = TRUE),
    prop_vax = vax_total / total,
    cases = rollapplyr(rowSums(.[grep("case", names(.))]), 9, sum, partial = TRUE),
    control = rollapplyr(rowSums(.[grep("control", names(.))]), 9, sum, partial = TRUE),
    vax_cases = rollapplyr(rowSums(.[grep("case_yes", names(.))]), 9, sum, partial = TRUE),
    vax_control = rollapplyr(rowSums(.[grep("control_yes", names(.))]), 9, sum, partial = TRUE),
    prop_case = vax_cases / cases,
    prop_control = vax_control / control,
    ve = NA,
    ve_lower = NA,
    ve_upper = NA
  )

# Calculate estimated VE and confidence intervals using the screening method - logistic regression version
# starting estimates at end of April when more stable
for (i in 14:nrow(screening_data)) {
  screening <- data.frame(
    cohort = c("group"),
    case = c(screening_data$cases[i]),
    vac = c(screening_data$vax_cases[i]),
    ppv = c(screening_data$prop_vax[i])
  )

  # Restructure dataset to fit model
  screening_2 <- screening %>%
    group_by(cohort, case, vac, ppv) %>%
    expand(count = 1:screening$case) %>%
    mutate(y = if_else(count <= vac, 1, 0)) %>%
    mutate(pcv = vac / case, logit_ppv = log(ppv / (1 - ppv))) %>%
    dplyr::select(-count)

  # Fit logistic regression
  model <- glm(y ~ 1 + offset(logit_ppv), data = screening_2, family = "binomial")


  # calculate VE estimates and confidence interval
  screening_data$ve[i] <- (1 - exp(coef(model))) * 100
  screening_data$ve_lower[i] <- (1 - exp(confint(model))[2]) * 100
  screening_data$ve_upper[i] <- (1 - exp(confint(model))[1]) * 100
}

# cut off negative lower limits at zero for ease of plotting
# screening_data$ve_lower <- ifelse(screening_data$ve_lower < 0, 0, screening_data$ve_lower)

# drop estimates sample size falls below 200
screening_data$ve <- ifelse(screening_data$total < 200, NA, screening_data$ve)
screening_data$ve_lower <- ifelse(screening_data$total < 200, NA, screening_data$ve_lower)
screening_data$ve_upper <- ifelse(screening_data$total < 200, NA, screening_data$ve_upper)

# select VE scenarios to model
ve_scenarios <- c(.9, .5, 0)

# calculate expected % of cases vaccinated
for (i in ve_scenarios) {
  screening_data[[paste("pcv", i, sep = "_")]] <- ((1 - i) / ((1 - screening_data$prop_vax) / screening_data$prop_vax)) / (1 + ((1 - i) / ((1 - screening_data$prop_vax) / screening_data$prop_vax)))
}


# screening method with booster  -------------------------------------------------
screening_boost <- dat %>%
  filter(week_date >= "2021-01-24", !is.na(fully_boosted)) %>%
  group_by(week_date, case_control, fully_boosted) %>%
  tally() %>%
  ungroup() %>%
  pivot_wider(id_cols = week_date, names_from = c(case_control, fully_boosted), values_from = n) %>%
  replace(is.na(.), 0) %>%
  # summing over 6-week windows
  mutate(
    total_boost = rollapplyr(rowSums(.[, 2:5]), 9, sum, partial = T),
    vax_total_boost = rollapplyr(rowSums(.[grep("yes", names(.))]), 9, sum, partial = T),
    prop_vax_boost = vax_total_boost / total_boost,
    cases_boost = rollapplyr(rowSums(.[grep("case", names(.))]), 9, sum, partial = T),
    control_boost = rollapplyr(rowSums(.[grep("control", names(.))]), 9, sum, partial = T),
    vax_cases_boost = rollapplyr(rowSums(.[grep("case_yes", names(.))]), 9, sum, partial = T),
    vax_control_boost = rollapplyr(rowSums(.[grep("control_yes", names(.))]), 9, sum, partial = T),
    prop_case_boost = vax_cases_boost / cases_boost,
    prop_control_boost = vax_control_boost / control_boost,
    boost_ve = NA,
    boost_ve_lower = NA,
    boost_ve_upper = NA
  ) %>%
  rename("case_no_boost" = "case_no", "control_no_boost" = "control_no", "case_yes_boost" = "case_yes", "control_yes_boost" = "control_yes")


# Calculate estimated VE and confidence intervals using the screening method - logistic regression version
# starting estimates at end of October
for (i in 47:nrow(screening_boost)) {
  screeningb2 <- data.frame(
    cohort = c("group"),
    case = c(screening_boost$cases_boost[i]),
    vac = c(screening_boost$vax_cases_boost[i]),
    ppv = c(screening_boost$prop_vax_boost[i])
  )

  # Restructure dataset to fit model
  screening_boost2 <- screeningb2 %>%
    group_by(cohort, case, vac, ppv) %>%
    expand(count = 1:screeningb2$case) %>%
    mutate(y = if_else(count <= vac, 1, 0)) %>%
    mutate(pcv = vac / case, logit_ppv = log(ppv / (1 - ppv))) %>%
    dplyr::select(-count)

  # Fit logistic regression
  model <- glm(y ~ 1 + offset(logit_ppv), data = screening_boost2, family = "binomial")


  # calculate VE estimates and confidence interval
  screening_boost$boost_ve[i] <- (1 - exp(coef(model))) * 100
  screening_boost$boost_ve_lower[i] <- (1 - exp(confint(model))[2]) * 100
  screening_boost$boost_ve_upper[i] <- (1 - exp(confint(model))[1]) * 100
}

# cut off negative lower limits at zero for ease of plotting
# screening_boost$boost_ve_lower <- ifelse(screening_boost$boost_ve_lower < 0, 0, screening_boost$boost_ve_lower)

# remove estimates if sample size <200
screening_boost$boost_ve <- ifelse(screening_boost$total_boost < 200, NA, screening_boost$boost_ve)
screening_boost$boost_ve_lower <- ifelse(screening_boost$total_boost < 200, NA, screening_boost$boost_ve_lower)
screening_boost$boost_ve_upper <- ifelse(screening_boost$total_boost < 200, NA, screening_boost$boost_ve_upper)

# calculate expected % of cases vaccinated for three scenarios with booster data
for (i in ve_scenarios) {
  screening_boost[[paste("pcv_boost", i, sep = "_")]] <- ((1 - i) / ((1 - screening_boost$prop_vax_boost) / screening_boost$prop_vax_boost)) / (1 + ((1 - i) / ((1 - screening_boost$prop_vax_boost) / screening_boost$prop_vax_boost)))
}


# Join all screening data
screening_all <- screening_data %>%
  left_join(screening_boost, by = "week_date")


screening_all <- screening_all %>%
  mutate(
    unvax_cases = cases - vax_cases,
    unvax_controls = control - vax_control,
    risk_unvax = unvax_cases / unvax_controls,
    risk_fully = vax_cases / vax_control,
    risk_boosted = vax_cases_boost / vax_control_boost
  )


# save data for Tableau Tab 1 Plot 2 - don't need anymore
# scan_vax_prop <- screening_all %>%
# select(week_date, prop_vax, prop_vax_boost) %>%
# pivot_longer(!week_date, names_to = "Vaccination Status", values_to = "% Vaccinated")
# write.csv(scan_vax_prop, "data/percent_vaccinated.csv", row.names = F)


# save data for Tableau Tab 2 Plot 1
probability <- screening_all %>%
  select(week_date, risk_unvax, risk_fully, risk_boosted) %>%
  pivot_longer(!week_date, names_to = "Vaccination Status", values_to = "Risk")

write.csv(probability, "data/infection_probability.csv", row.names = F)


# save data for Tableau Tab 2 Plot 2
ve_estimate <- screening_all %>%
  select(week_date, ve_lower, ve, ve_upper, boost_ve_lower, boost_ve, boost_ve_upper)

write.csv(ve_estimate, "data/ve_estimate.csv", row.names = F)


# save data for Tableau Tab 2 Plot 3
ve_scenario <- screening_all %>%
  select(week_date, pcv_0, pcv_0.5, pcv_0.9, pcv_boost_0, pcv_boost_0.5, pcv_boost_0.9, prop_case, prop_case_boost) %>%
  pivot_longer(!week_date, names_to = "VE Scenarios", values_to = "% Cases Vaccinated")

write.csv(ve_scenario, "data/ve_scenario.csv", row.names = F)


# Run models  -------------------------------------------------------------
# There are the regression models

# If we ever have bugs with the code we should make sure this web address hasn't changed
case_data <- read_csv("https://raw.githubusercontent.com/nytimes/covid-19-data/master/us-counties.csv", show_col_types = F) %>%
  filter(state == "Washington", county == "King") %>%
  mutate(
    new_cases = cases - lag(cases, 1),
    mmwr_week(date),
    week_date = mmwr_week_to_date(week = mmwr_week, year = mmwr_year)
  ) %>%
  group_by(week_date) %>%
  summarize(cases = sum(new_cases)) %>%
  ungroup() %>%
  mutate(incidence_indicator = rollmean(cases, 5, align = "right", fill = NA))

# join incidence data with other data
dat <- dat %>%
  left_join(case_data, by = "week_date")

# get probabilities for OR - relative risk conversion
p1 <- with(dat, prop.table(table(case_control_bin, regression_doses)))[2, 1]
p2 <- with(dat %>% filter(encountered >= "2021-06-01", encountered <= "2022-01-31"), prop.table(table(delta_case, regression_doses)))[2, 1]
p3 <- with(dat %>% filter(encountered >= "2021-12-12"), prop.table(table(omicron_case, regression_doses)))[2, 1]


# All Variants
mod1 <- glm(case_control_bin ~ regression_doses + week_num + incidence_indicator + alpha + delta + omicron + prior_infection + age_group + region + race_ethnicity_recode + sex, data = dat, family = "binomial")
mod1_dat <- as.data.frame(exp(cbind(coef(mod1), confint(mod1))))[2:4, ]
names(mod1_dat) <- c("OR", "lower", "upper")
mod1_dat$doses <- c("2 Doses >6m ago", "2 Doses <6m ago", "3 Doses")
mod1_dat$variant <- "All Variants (January 2021-Present)"
mod1_dat <- mod1_dat %>% mutate(
  VE = round((1 - OR) * 100, 1),
  VE_lower = round((1 - upper) * 100, 1),
  VE_upper = round((1 - lower) * 100, 1),
  doses = factor(doses, levels = c("3 Doses", "2 Doses <6m ago", "2 Doses >6m ago")),
  rel_risk = OR / (1 - p1 + (p1 * OR)),
  rel_risk = 1 / rel_risk
)



# Delta Specific
mod2 <- glm(delta_case ~ regression_doses + week_num + prior_infection + incidence_indicator + age_group + region + race_ethnicity_recode + sex, data = dat %>% filter(encountered >= "2021-06-01", encountered <= "2022-01-31"), family = "binomial")
mod2_dat <- as.data.frame(exp(cbind(coef(mod2), confint(mod2))))[2:4, ]
names(mod2_dat) <- c("OR", "lower", "upper")
mod2_dat$doses <- c("2 Doses >6m ago", "2 Doses <6m ago", "3 Doses")
mod2_dat$variant <- "Delta Specific (April 2021 - Present)"
mod2_dat <- mod2_dat %>% mutate(
  VE = round((1 - OR) * 100, 1),
  VE_lower = round((1 - upper) * 100, 1),
  VE_upper = round((1 - lower) * 100, 1),
  doses = factor(doses, levels = c("3 Doses", "2 Doses <6m ago", "2 Doses >6m ago")),
  rel_risk = OR / (1 - p2 + (p2 * OR)),
  rel_risk = 1 / rel_risk
)

# Omicron Specific
mod3 <- glm(omicron_case ~ regression_doses + week_num + incidence_indicator + age_group + region + race_ethnicity_recode + sex, data = dat %>% filter(encountered >= "2021-12-12", prior_infection == 0), family = "binomial")
mod3_dat <- as.data.frame(exp(cbind(coef(mod3), confint(mod3))))[2:4, ]
names(mod3_dat) <- c("OR", "lower", "upper")
mod3_dat$doses <- c("2 Doses >6m ago", "2 Doses <6m ago", "3 Doses")
mod3_dat$variant <- "Omicron Specific (December 2021 - Present)"
mod3_dat <- mod3_dat %>% mutate(
  VE = round((1 - OR) * 100, 1),
  VE_lower = round((1 - upper) * 100, 1),
  VE_upper = round((1 - lower) * 100, 1),
  doses = factor(doses, levels = c("3 Doses", "2 Doses <6m ago", "2 Doses >6m ago")),
  rel_risk = OR / (1 - p2 + (p2 * OR)),
  rel_risk = 1 / rel_risk
)



# combine datasets
# select variables
# cut off lower CIs if <0
VE_dat <- rbind(mod1_dat, mod2_dat, mod3_dat) %>%
  mutate(range = VE_upper - VE_lower) %>%
  filter(range < 80) %>%
  select(doses, variant, VE_lower, VE, VE_upper, rel_risk) %>%
  mutate(VE_lower = ifelse(VE_lower < 0, 0, VE_lower))


write.csv(VE_dat, "data/ve_variant.csv", row.names = F)
# This dataframe is used to make the VE whisker plots in Tableau
